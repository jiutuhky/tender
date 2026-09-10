import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessageChunk

from hagent.model_retry.policy import ModelCallFailed, classify_error
from hagent.model_retry.runtime import cancel_run, register_run, release_run
from hagent.server.model_stream import stream_agent_events
from hagent.server.routers.messages import cancel_message_run
from hagent.server.workspace_checkpoint import CheckpointResult, CheckpointFailure


def unpack(frames):
    events = []
    for frame in frames:
        lines = frame.decode().splitlines()
        event = next((line[7:] for line in lines if line.startswith("event: ")), None)
        data = next((json.loads(line[6:]) for line in lines if line.startswith("data: ")), {})
        if event:
            events.append((event, data))
    return events


@pytest.fixture
def checkpoint(monkeypatch):
    calls = []
    monkeypatch.setattr("hagent.server.model_stream.append_transcript", lambda *args: None)
    def save(**kwargs):
        calls.append(kwargs)
        return CheckpointResult("r", "commit", ("成果.md",))
    return calls, save


@pytest.mark.asyncio
async def test_cancel_waiting_request_heartbeat_and_cleanup(checkpoint, monkeypatch):
    calls, save = checkpoint
    monkeypatch.setattr("hagent.server.model_stream.HEARTBEAT_SECONDS", 0.02)
    class WaitingAgent:
        closed = False
        async def astream(self, *args, **kwargs):
            try:
                await asyncio.sleep(100)
                yield None
            finally:
                self.closed = True
    agent = WaitingAgent()
    stream = stream_agent_events(agent, "请求", "s", run_id="r", checkpoint=save)
    frames = [await anext(stream), await asyncio.wait_for(anext(stream), .4)]
    assert frames[-1] == b": heartbeat\n\n"
    assert cancel_run("r") and cancel_run("r")
    frames.extend([frame async for frame in stream])
    assert agent.closed
    assert len(calls) == 1 and calls[0]["interrupted"]
    events = unpack(frames)
    assert events[-1][0] == "run.cancelled" and events[-1][1]["checkpoint_saved"]
    assert not cancel_run("r")


@pytest.mark.asyncio
async def test_client_disconnect_closes_task_and_checkpoints(checkpoint):
    calls, save = checkpoint
    closed = asyncio.Event()
    class Agent:
        async def astream(self, *args, **kwargs):
            try:
                yield (), "messages", (AIMessageChunk(content="半截"), {})
                await asyncio.sleep(100)
            finally:
                closed.set()
    stream = stream_agent_events(Agent(), "请求", "s", run_id="r", checkpoint=save)
    await anext(stream)
    await anext(stream)
    await stream.aclose()
    assert closed.is_set()
    assert len(calls) == 1 and calls[0]["interrupted"]


@pytest.mark.asyncio
async def test_failure_output_reset_and_saved_claim(monkeypatch, checkpoint):
    calls, save = checkpoint
    transcript = []
    monkeypatch.setattr("hagent.server.model_stream.append_transcript", lambda *args: transcript.append(args))
    class Agent:
        async def astream(self, *args, **kwargs):
            for attempt, text in [(1, "失败正文"), (2, "成功正文")]:
                data = {"model_call_id": "m", "attempt": attempt, "run_id": "r", "parent_tool_use_id": None}
                yield (), "custom", {"event": "model.attempt.started", "data": data}
                yield (), "messages", (AIMessageChunk(content=[{"type": "text", "text": text}]), data)
                if attempt == 1:
                    yield (), "custom", {"event": "model.retry", "data": data}
                    yield (), "messages", (AIMessageChunk(content="迟到"), data)
                else:
                    yield (), "custom", {"event": "model.call.completed", "data": data}
    frames = [frame async for frame in stream_agent_events(Agent(), "请求", "s", run_id="r", checkpoint=save)]
    assert transcript == [("s", "assistant", "成功正文")]
    assert b"\xe8\xbf\x9f\xe5\x88\xb0" not in b"".join(frames)
    assert unpack(frames)[-1] == ("done", {"thread_id": "s", "checkpoint_saved": True})


@pytest.mark.asyncio
async def test_fatal_failure_does_not_claim_saved_when_checkpoint_failed(checkpoint):
    class Agent:
        async def astream(self, *args, **kwargs):
            raise ModelCallFailed(classify_error(ConnectionError()), 11, {"model_call_id": "m", "parent_tool_use_id": "parent"})
            yield
    def broken(**kwargs):
        raise CheckpointFailure("失败", result=CheckpointResult("r", "partial", ()))
    events = unpack([frame async for frame in stream_agent_events(Agent(), "请求", "s", run_id="r", checkpoint=broken)])
    assert events[-1][0] == "error"
    data = events[-1][1]
    assert data["attempts"] == 11 and data["attempt"] == 11
    assert data["parent_tool_use_id"] == "parent"
    assert data["checkpoint_saved"] is False
    assert sum(e == "error" for e,_ in events) == 1


def test_cancel_endpoint_ownership_and_idempotency(monkeypatch):
    from hagent.server.runs import RunStatus
    run = SimpleNamespace(session_id="s", project_id="p", status=RunStatus.RUNNING)
    manager = SimpleNamespace(run_store=SimpleNamespace(get=lambda _: run))
    monkeypatch.setattr("hagent.server.routers.messages.get_store", lambda: SimpleNamespace(get=lambda _: SimpleNamespace(project_id="p")))
    monkeypatch.setattr("hagent.server.routers.messages.get_session_manager", lambda: manager)
    register_run("r")
    try:
        assert cancel_message_run("s", "r")["accepted"]
        assert cancel_message_run("s", "r")["accepted"]
        with pytest.raises(HTTPException) as error:
            cancel_message_run("other-session", "r")
        assert error.value.status_code == 404
        run.status = RunStatus.COMMITTED
        assert cancel_message_run("s", "r")["status"] == "committed"
    finally:
        release_run("r")

@pytest.mark.asyncio
async def test_shared_namespace_parallel_tool_arguments_stay_with_their_attempt(checkpoint):
    _, save = checkpoint
    class Agent:
        async def astream(self, *args, **kwargs):
            a = {"model_call_id": "a", "attempt": 1, "parent_tool_use_id": "pa"}
            b = {"model_call_id": "b", "attempt": 1, "parent_tool_use_id": "pb"}
            for metadata, id in [(a, "ta"), (b, "tb")]:
                yield ("shared",), "custom", {"event": "model.attempt.started", "data": metadata}
                yield ("shared",), "messages", (AIMessageChunk(content="", tool_call_chunks=[{"name": "Write", "id": id, "index": 0, "args": '{"file":'}]), metadata)
            yield ("shared",), "custom", {"event": "model.retry", "data": a}
            yield ("shared",), "messages", (AIMessageChunk(content="", tool_call_chunks=[{"name": None, "id": None, "index": 0, "args": '"成功.md"}'}]), b)
    events = unpack([frame async for frame in stream_agent_events(Agent(), "请求", "s", run_id="r", checkpoint=save)])
    last = [data for event, data in events if event == "tool_call.started"][-1]
    assert last["call_id"] == "tb" and last["parent_tool_use_id"] == "pb"
    assert last["model_call_id"] == "b"
