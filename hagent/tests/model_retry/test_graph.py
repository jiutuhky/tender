"""通过真实 Anthropic SDK + LangChain 图消费模拟 HTTP/SSE，验证工具与历史边界。"""
import json
import sqlite3

import anthropic
import httpx
import pytest
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

from hagent.model_retry import ModelRetryMiddleware, ModelRetryPolicy
from hagent.server.agents import AsyncCompatibleSqliteSaver
from hagent.server.sse import parse_lg_chunk


def frame(kind, **data):
    return f"event: {kind}\ndata: {json.dumps({'type': kind, **data})}\n\n"


def response(*, text=None, tool_id=None, incomplete=False):
    content = frame("message_start", message={"id": "msg-test", "type": "message", "role": "assistant", "model": "test", "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 5, "output_tokens": 0}})
    if tool_id:
        content += frame("content_block_start", index=0, content_block={"type": "tool_use", "id": tool_id, "name": "save_result", "input": {}})
        content += frame("content_block_delta", index=0, delta={"type": "input_json_delta", "partial_json": '{"text":' if incomplete else '{"text":"成果"}'})
    else:
        content += frame("content_block_start", index=0, content_block={"type": "text", "text": ""})
        content += frame("content_block_delta", index=0, delta={"type": "text_delta", "text": text or "回复"})
    if not incomplete:
        content += frame("content_block_stop", index=0)
        content += frame("message_delta", delta={"stop_reason": "tool_use" if tool_id else "end_turn", "stop_sequence": None}, usage={"output_tokens": 8})
        content += frame("message_stop")
    return httpx.Response(200, text=content, headers={"content-type": "text/event-stream"})


@pytest.fixture
def transport(monkeypatch):
    replies, requests, clients = [], [], []
    def send(request):
        requests.append(json.loads(request.content))
        assert request.url.path == "/v1/messages"
        reply = replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply
    def factory(params):
        assert params["max_retries"] == 0
        client = anthropic.AsyncAnthropic(**params, http_client=httpx.AsyncClient(transport=httpx.MockTransport(send)))
        clients.append(client)
        return client
    monkeypatch.setattr("hagent.model_retry.anthropic.new_async_client", factory)
    return replies, requests, clients


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.asyncio
async def test_partial_tool_is_retried_without_duplicate_execution_or_history(transport, tmp_path, asynchronous):
    replies, requests, clients = transport
    replies.extend([response(tool_id="bad", incomplete=True), response(tool_id="good"), response(text="已完成")])
    effects = []
    @tool
    def save_result(text: str) -> str:
        """保存已生成成果。"""
        effects.append(text)
        return "已保存"
    saver = AsyncCompatibleSqliteSaver(sqlite3.connect(tmp_path / "thread.db", check_same_thread=False))
    graph = create_agent(ChatAnthropic(model="test", api_key="test-key", base_url="https://model.test"), [save_result],
                         middleware=[ModelRetryMiddleware(ModelRetryPolicy(base_ms=1, max_delay_ms=1))], checkpointer=saver)
    config = {"configurable": {"thread_id": "t"}, "metadata": {"run_id": "r", "parent_tool_use_id": "parent"}}
    kwargs = dict(config=config, stream_mode=["messages", "custom", "updates"], subgraphs=True)
    if asynchronous:
        chunks = [chunk async for chunk in graph.astream({"messages": [{"role": "user", "content": "保存"}]}, **kwargs)]
    else:
        chunks = list(graph.stream({"messages": [{"role": "user", "content": "保存"}]}, **kwargs))
    assert effects == ["成果"]
    assert len(requests) == 3
    assert requests[0]["messages"] == requests[1]["messages"]
    assert all(client.is_closed() for client in clients)
    events = [event for _, mode, payload in chunks for event in parse_lg_chunk((mode, payload))]
    attempts = [data for event, data in events if event == "model.attempt.started"]
    assert [d["attempt"] for d in attempts] == [1, 2, 1]
    assert attempts[0]["model_call_id"] == attempts[1]["model_call_id"] != attempts[2]["model_call_id"]
    deltas = [data for event, data in events if event == "tool_call.started"]
    assert deltas and all(d["model_call_id"] and d["attempt"] and d["run_id"] == "r" and d["parent_tool_use_id"] == "parent" for d in deltas)
    messages = graph.get_state(config).values["messages"]
    assert not any(call["id"] == "bad" for msg in messages for call in getattr(msg, "tool_calls", []))
    assert sum(len(getattr(msg, "tool_calls", [])) for msg in messages) == 1


@pytest.mark.asyncio
async def test_http_200_overload_and_connection_retry(transport):
    replies, requests, clients = transport
    replies.extend([
        httpx.ConnectError("TLS EOF"),
        httpx.Response(200, text=frame("error", error={"type": "overloaded_error", "message": "overloaded"}), headers={"content-type": "text/event-stream"}),
        response(text="恢复成功"),
    ])
    graph = create_agent(ChatAnthropic(model="test", api_key="test-key", base_url="https://model.test"), [], middleware=[ModelRetryMiddleware(ModelRetryPolicy(base_ms=1))])
    chunks = [chunk async for chunk in graph.astream({"messages": [{"role": "user", "content": "测试"}]}, stream_mode=["messages", "custom"], subgraphs=True)]
    events = [event for _, mode, payload in chunks for event in parse_lg_chunk((mode, payload))]
    assert [d["category"] for e,d in events if e == "model.retry"] == ["connection", "overloaded"]
    assert len(requests) == 3
    assert all(c.is_closed() for c in clients)

@pytest.mark.asyncio
async def test_parallel_subagent_failure_stops_parent_and_closes_sibling(monkeypatch, tmp_path):
    import asyncio
    from hagent.model_retry import ModelCallFailed
    from hagent.subagents.agent_tool import build_agent_tool
    from hagent.tool_error_guard import ToolErrorGuardMiddleware
    from hagent.server.model_stream import stream_agent_events
    from hagent.server.workspace_checkpoint import CheckpointResult
    from tests.model_retry.test_run_stream import unpack

    counts = {"main": 0, "fail": 0, "slow": 0}
    closed, clients = [], []
    saved = tmp_path / "已有成果.md"
    saved.write_text("此前工具产物")
    parent_response = frame("message_start", message={"id": "parent", "type": "message", "role": "assistant", "model": "test", "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 0}})
    for i, name in enumerate(["fail", "slow"]):
        parent_response += frame("content_block_start", index=i, content_block={"type": "tool_use", "id": f"child-{name}", "name": "Agent", "input": {}})
        parent_response += frame("content_block_delta", index=i, delta={"type": "input_json_delta", "partial_json": json.dumps({"description": name, "prompt": name, "subagent_type": "general-purpose"})})
        parent_response += frame("content_block_stop", index=i)
    parent_response += frame("message_delta", delta={"stop_reason": "tool_use", "stop_sequence": None}, usage={"output_tokens": 20}) + frame("message_stop")
    async def send(request):
        data = json.loads(request.content)
        prompt = data["messages"][-1]["content"]
        if isinstance(prompt, list):
            prompt = "".join(block.get("text", "") for block in prompt)
        if prompt == "fail":
            counts["fail"] += 1
            await asyncio.sleep(.03)
            return httpx.Response(529, json={"error": {"type": "overloaded_error", "message": "overloaded"}})
        if prompt == "slow":
            counts["slow"] += 1
            try:
                await asyncio.sleep(100)
            finally:
                closed.append("slow")
        counts["main"] += 1
        return httpx.Response(200, text=parent_response, headers={"content-type": "text/event-stream"})
    def factory(params):
        client = anthropic.AsyncAnthropic(**params, http_client=httpx.AsyncClient(transport=httpx.MockTransport(send)))
        clients.append(client)
        return client
    monkeypatch.setattr("hagent.model_retry.anthropic.new_async_client", factory)
    policy = ModelRetryPolicy(max_retries=1, base_ms=1)
    model = ChatAnthropic(model="test", api_key="test-key", base_url="https://model.test")
    child = create_agent(model, [], middleware=[ModelRetryMiddleware(policy), ToolErrorGuardMiddleware()])
    agent_tool = build_agent_tool({"general-purpose": child}, "委派子任务")
    graph = create_agent(model, [agent_tool], middleware=[ModelRetryMiddleware(policy), ToolErrorGuardMiddleware()])
    checkpoints = []
    def checkpoint(**kwargs):
        checkpoints.append(kwargs)
        return CheckpointResult("parallel", "commit", (saved.name,))
    events = unpack([frame async for frame in stream_agent_events(graph, "main", "parallel-session", run_id="parallel", checkpoint=checkpoint)])
    assert events[-1][0] == "error"
    assert events[-1][1]["category"] == "overloaded"
    assert events[-1][1]["attempts"] == 2
    assert counts == {"main": 1, "fail": 2, "slow": 1}
    assert closed == ["slow"] and all(client.is_closed() for client in clients)
    assert saved.read_text() == "此前工具产物"
    retries = [d for e,d in events if e == "model.retry"]
    assert retries[0]["parent_tool_use_id"] == "child-fail"
    assert retries[0]["run_id"] == "parallel"
    assert checkpoints[0]["interrupted"]

@pytest.mark.parametrize("phase", ["headers", "stream", "backoff"])
@pytest.mark.asyncio
async def test_cancel_actual_transport_at_each_wait(monkeypatch, phase):
    import asyncio
    from hagent.model_retry.runtime import cancel_run
    from hagent.server.model_stream import stream_agent_events
    from tests.model_retry.test_run_stream import unpack
    clients, reads_closed = [], []
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield frame("message_start", message={"id": "m", "type": "message", "role": "assistant", "model": "test", "content": [], "stop_reason": None, "usage": {"input_tokens": 1, "output_tokens": 0}}).encode()
            try:
                await asyncio.sleep(100)
            finally:
                reads_closed.append("stream")
        async def aclose(self):
            reads_closed.append("body")
    async def send(request):
        if phase == "headers":
            try:
                await asyncio.sleep(100)
            finally:
                reads_closed.append("headers")
        if phase == "stream":
            return httpx.Response(200, stream=Body(), headers={"content-type": "text/event-stream"})
        return httpx.Response(529, json={"error": {"type": "overloaded_error"}}, headers={"retry-after": "3600"})
    def factory(params):
        client = anthropic.AsyncAnthropic(**params, http_client=httpx.AsyncClient(transport=httpx.MockTransport(send)))
        clients.append(client)
        return client
    monkeypatch.setattr("hagent.model_retry.anthropic.new_async_client", factory)
    graph = create_agent(ChatAnthropic(model="test", api_key="test-key", base_url="https://model.test"), [], middleware=[ModelRetryMiddleware(ModelRetryPolicy())])
    stream = stream_agent_events(graph, "请求", "cancel-s", run_id="cancel-r")
    frames = [await anext(stream)]
    if phase == "backoff":
        while not any(e == "model.retry" for e,_ in unpack(frames)):
            frames.append(await asyncio.wait_for(anext(stream), 1))
    else:
        frames.append(await anext(stream))
        await asyncio.sleep(.03)
    assert cancel_run("cancel-r")
    async def finish():
        return [frame async for frame in stream]
    frames.extend(await asyncio.wait_for(finish(), 1))
    assert unpack(frames)[-1][0] == "run.cancelled"
    assert all(client.is_closed() for client in clients)
    assert len(clients) == 1
    if phase in ("headers", "stream"):
        assert phase in reads_closed
