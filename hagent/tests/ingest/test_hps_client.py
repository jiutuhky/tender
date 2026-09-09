"""Triton 封装、业务错误和跨页输入的协议回归。"""
import json
import httpx
import pytest
from hagent.ingest.ocr_client import OcrClient, OcrSettings, OcrServiceError, _RawPage


def wrapped(payload):
    return {"outputs": [{"name": "output", "data": [json.dumps(payload)]}]}


def test_layout_request_uses_triton_and_disables_preprocessing():
    seen = []
    def handle(request):
        seen.append(request)
        return httpx.Response(200, json=wrapped({"errorCode": 0, "result": {"layoutParsingResults": []}}))
    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        OcrClient(OcrSettings(base_url="http://hps:8000"), client=transport)._layout_parsing(b"pdf")
    r = seen[0]
    assert str(r.url) == "http://hps:8000/v2/models/layout-parsing/infer"
    tensor = json.loads(r.content)["inputs"][0]
    assert tensor["shape"] == [1, 1] and tensor["datatype"] == "BYTES"
    body = json.loads(tensor["data"][0])
    assert body["fileType"] == 0 and body["file"] == "cGRm"
    assert body["useDocOrientationClassify"] is body["useDocUnwarping"] is False
    assert body["visualize"] is False


@pytest.mark.parametrize("body", [wrapped({"errorCode": 500, "errorMsg": "failed"}), {}, wrapped({"result": {}}), wrapped({"errorCode": 0})])
def test_http_200_is_not_business_success(body):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))) as transport:
        with pytest.raises(OcrServiceError):
            OcrClient(client=transport)._layout_parsing(b"pdf")


def test_restructure_maps_markdown_images_and_preserves_pages():
    entry = {"prunedResult": {"width": 100, "height": 200}, "markdown": {"text": "内容", "images": {"x.png": "aW1n"}}}
    def handle(request):
        body = json.loads(json.loads(request.content)["inputs"][0]["data"][0])
        assert request.url.path == "/v2/models/restructure-pages/infer"
        assert body["concatenatePages"] is False
        assert body["pages"] == [{"prunedResult": entry["prunedResult"], "markdownImages": {"x.png": "aW1n"}}]
        return httpx.Response(200, json=wrapped({"errorCode": 0, "result": {"layoutParsingResults": [entry]}}))
    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        result = OcrClient(client=transport)._restructure([_RawPage(7, entry, {"width": 100, "height": 200})])
    assert result[0].index == 7 and result[0].info["width"] == 100


def test_unreachable_service_is_not_retried_for_every_page():
    calls = []
    def handle(request):
        calls.append(request)
        raise httpx.ConnectError("unreachable", request=request)
    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        from pypdf import PdfWriter
        import io
        writer = PdfWriter()
        for _ in range(20):
            writer.add_blank_page(width=100, height=100)
        buffer = io.BytesIO(); writer.write(buffer)
        with pytest.raises(OcrServiceError, match="无法连接"):
            OcrClient(client=transport).parse_pdf(buffer.getvalue())
    assert len(calls) == 1


def test_missing_middle_page_is_recovered_without_shifting_sources():
    """批次少还页时无法证明缺页位置，拆到单页后恢复各自的真实归属。"""
    import io
    import base64
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=200)
    writer.add_blank_page(width=150, height=200)
    output = io.BytesIO(); writer.write(output)
    calls = []
    def handle(request):
        body = json.loads(json.loads(request.content)["inputs"][0]["data"][0])
        pages = PdfReader(io.BytesIO(base64.b64decode(body["file"]))).pages
        calls.append(len(pages))
        # 双页请求模拟漏掉前页，只返回后页。
        page = pages[-1]
        content = "前页" if page.mediabox.width == 100 else "后页"
        entry = {"prunedResult": {"width": int(page.mediabox.width), "height": 200,
                 "parsing_res_list": [{"block_label": "text", "block_content": content, "block_bbox": [0, 0, 50, 50]}]},
                 "markdown": {"text": content}}
        return httpx.Response(200, json=wrapped({"errorCode": 0, "result": {"layoutParsingResults": [entry]}}))
    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        result = OcrClient(OcrSettings(restructure=False), client=transport).parse_pdf(output.getvalue())
    assert [p.index for p in result] == [0, 1]
    assert [p.markdown for p in result] == ["前页", "后页"]
    assert calls == [2, 1, 1]
