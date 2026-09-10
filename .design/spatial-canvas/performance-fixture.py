"""画布验收专用契约服务；仅监听本机，不访问模型或真实项目。"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
TYPES = ("basic_info", "business", "technical", "scoring")
COUNTS = {"basic_info": 0, "business": 60, "technical": 60, "scoring": 80}
TEXT = "应提交完整的实施方案，明确交付里程碑、质量保障、人员配置和运维服务。" * 12
BODY = f"## 编制要求\n\n{TEXT}\n\n| 阶段 | 交付物 |\n| --- | --- |\n| 实施 | 验收报告 |\n| 运维 | 服务记录 |\n\n{TEXT}"
REFS = [{"document_id": "doc-1", "line_span": [3, 6], "section": "技术与服务要求"}]
FILES = [{"path": "sources/01-招标文件.md", "size": 18000},
         {"path": "sources/02-现场参考.webp", "size": 150000}] + [
    {"path": f"sources/资料-{i:03}.md", "size": 18000} for i in range(98)]
DOC = {"id": "doc-1", "path": FILES[0]["path"], "sha256": "b" * 64,
       "origin_sha256": "a" * 64, "preview_sha256": "a" * 64,
       "has_preview": True, "doc_type": "tender", "registered_at": "2026-09-10T00:00:00Z", "created": False}
END_STREAM = threading.Event()
ROWS = {}
for kind in TYPES:
    rows = []
    for i in range(COUNTS[kind]):
        item_id = f"{kind}-{i:03}"
        payload = {"id": item_id, "title": f"{'评分要点' if kind == 'scoring' else '响应要求'} {i + 1:03}",
                   "source_refs": REFS}
        if kind == "scoring":
            payload.update(group="technical", subgroup="实施方案", max_score=2,
                           scoring_rule=BODY, related_format="技术文件")
        else:
            payload.update(requirement_text=BODY, mandatory=i % 5 == 0,
                           evidence_required=["实施计划", "项目人员安排"])
        rows.append({"matrix_type": kind, "stage": "published", "item_id": item_id,
                     "section": "items", "payload": payload, "response_status": "pending",
                     "response_note": None, "confirmed": False, "version": 1})
    ROWS[kind] = rows


def project(pid):
    return {"id": pid, "name": f"画布性能验收 {pid}", "status": "parsed",
            "created_at": 1788998400, "updated_at": 1788998400,
            "metadata": {}, "latest_session": None}


def pdf_bytes():
    """一页文字 PDF，供真实 PDF.js 缩略图和原文入口加载。"""
    stream = b"BT /F1 24 Tf 72 750 Td (Canvas performance fixture) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    result, offsets = b"%PDF-1.4\n", [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n"
    result += b"".join(f"{n:010} 00000 n \n".encode() for n in offsets[1:])
    return result + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, value, content_type="application/json", status=200):
        data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        parts = unquote(url.path).strip("/").split("/")
        query = parse_qs(url.query)
        if parts == ["projects"]:
            return self.reply([project("perf-a"), project("perf-b")])
        if parts == ["samples"]:
            return self.reply([])
        if parts[0] != "projects":
            return self.reply({"detail": "验收路径不存在"}, status=404)
        pid = parts[1]
        if len(parts) == 2:
            return self.reply(project(pid))
        if parts[2:] == ["workspace", "files"]:
            return self.reply(FILES)
        if parts[2:4] == ["workspace", "files"]:
            if parts[-1].endswith(".webp"):
                return self.reply((ROOT / "frontend/public/canvas-demo/desk.webp").read_bytes(), "image/webp")
            return self.reply(("# 项目资料\n\n" + BODY).encode(), "text/markdown; charset=utf-8")
        if parts[2] == "documents":
            if len(parts) == 3:
                return self.reply({"documents": [DOC], "total_count": 1, "limit": 100,
                                   "offset": 0, "has_more": False, "next_offset": None})
            return self.reply(pdf_bytes(), "application/pdf")
        if parts[2] == "matrices":
            if len(parts) == 3:
                return self.reply({"project_id": pid, "matrices": [
                    {"matrix_type": t, "state": "published", "current_rev": 1,
                     "updated_at": None, "draft_count": 0, "current_count": COUNTS[t],
                     "last_validation": None} for t in TYPES]})
            kind = parts[3]
            if len(parts) == 4:
                meta = {"schema_version": "1", "matrix_type": kind, "project_id": pid}
                if kind == "basic_info":
                    meta["project"] = {"name": project(pid)["name"], "scope": TEXT,
                                       "purchaser": {"name": "项目建设单位"}}
                if kind == "scoring":
                    meta["evaluation"] = {"total_score": 100, "technical_score": 60,
                                          "business_score": 20, "price_score": 20}
                return self.reply({"matrix_type": kind, "state": "published", "current_rev": 1,
                                   "updated_at": None, "meta": meta,
                                   "stats": {"stage": "published", "total": COUNTS[kind],
                                             "by_section": {"items": COUNTS[kind]},
                                             "by_response_status": {}, "confirmed_count": 0,
                                             "mandatory_count": 0, "by_category": {}}})
            offset, limit = int(query.get("offset", [0])[0]), int(query.get("limit", [100])[0])
            rows = ROWS[kind]
            more = offset + limit < len(rows)
            return self.reply({"items": rows[offset:offset+limit], "total_count": len(rows),
                               "limit": limit, "offset": offset, "has_more": more,
                               "next_offset": offset + limit if more else None})
        self.reply({"detail": "验收路径不存在"}, status=404)

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        parts = self.path.strip("/").split("/")
        if parts == ["__finish"]:
            END_STREAM.set()
            return self.reply({"ok": True})
        if parts == ["sessions"]:
            return self.reply({"session_id": f"session-{data['project_id']}"})
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "messages":
            return self.stream(data.get("content", ""))
        if "confirm" in parts or "response-status" in parts:
            row = next(r for r in ROWS[parts[3]] if r["item_id"] == parts[5])
            row.update(confirmed=True, version=row["version"] + 1)
            return self.reply(row)
        self.reply({"detail": "验收路径不存在"}, status=404)

    def stream(self, content):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        index = 0

        def emit(event, data):
            nonlocal index
            self.wfile.write(f"id: {index}\nevent: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()
            index += 1

        try:
            emit("run.started", {"run_id": "perf-run"})
            emit("todo.updated", {"todos": [{"id": str(i), "content": f"核验阶段 {i}",
                 "status": "completed" if i == 0 else "in_progress", "blockedBy": []} for i in range(3)]})
            for i in range(20):
                emit("tool_call.started", {"call_id": f"perf-tool-{i}", "tool_name": "Read",
                     "args_chunk": '{"path":"sources/招标文件.md"}', "parent_tool_use_id": None})
                emit("tool_call.completed", {"call_id": f"perf-tool-{i}", "tool_name": "Read",
                     "result_summary": TEXT, "parent_tool_use_id": None})
            if "持续" in content:
                END_STREAM.clear()
                for i in range(600):
                    if END_STREAM.is_set():
                        break
                    emit("message.delta", {"role": "assistant", "content_chunk": f"正在核验第 {i+1} 项要求。\n\n", "parent_tool_use_id": None})
                    time.sleep(0.1)
            else:
                emit("message.delta", {"role": "assistant", "content_chunk": "# 编制成果\n\n" + BODY * 10, "parent_tool_use_id": None})
            emit("todo.updated", {"todos": [{"id": str(i), "content": f"核验阶段 {i}",
                 "status": "completed", "blockedBy": []} for i in range(3)]})
            emit("done", {})
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    print("画布契约服务：http://127.0.0.1:8108", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8108), Handler).serve_forever()
