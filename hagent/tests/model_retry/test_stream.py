import asyncio
import threading
from types import SimpleNamespace as Obj

import pytest

from hagent.model_retry.anthropic import guarded_stream, guarded_astream, StreamWatchdog
from hagent.model_retry.policy import IncompleteResponseError, ModelRetryPolicy, ModelTimeoutError
from hagent.model_retry.runtime import AttemptContext, attempt_context


class Stream:
    def __init__(self, events):
        self.events, self.closed = events, False
    def __iter__(self):
        return iter(self.events)
    def close(self):
        self.closed = True


class AsyncStream(Stream):
    async def __aiter__(self):
        for event in self.events:
            yield event
    async def close(self):
        self.closed = True


@pytest.mark.parametrize("events", [[], [Obj(type="message_stop")], [Obj(type="message_start")], [Obj(type="message_start"), Obj(type="content_block_delta", delta=Obj(text="半截正文"))], [Obj(type="content_block_delta", delta=Obj(partial_json='{"file":'))]])
@pytest.mark.asyncio
async def test_incomplete_both_paths(events):
    sync, async_ = Stream(events), AsyncStream(events)
    with pytest.raises(IncompleteResponseError):
        list(guarded_stream(sync, ModelRetryPolicy()))
    with pytest.raises(IncompleteResponseError):
        _ = [event async for event in guarded_astream(async_, ModelRetryPolicy())]
    assert sync.closed and async_.closed


@pytest.mark.asyncio
async def test_complete_both_paths():
    events = [Obj(type="message_start"), Obj(type="message_stop")]
    assert len(list(guarded_stream(Stream(events), ModelRetryPolicy()))) == 2
    assert len([event async for event in guarded_astream(AsyncStream(events), ModelRetryPolicy())]) == 2


@pytest.mark.asyncio
async def test_idle_timeout_closes_pending_read_and_warns():
    class HangingStream(AsyncStream):
        async def __aiter__(self):
            yield Obj(type="message_start")
            try:
                await asyncio.sleep(100)
            finally:
                self.reader_cancelled = True
    stream = HangingStream([])
    events = []
    token = attempt_context.set(AttemptContext({"model_call_id": "m", "attempt": 1}, lambda *event: events.append(event)))
    try:
        with pytest.raises(ModelTimeoutError):
            _ = [e async for e in guarded_astream(stream, ModelRetryPolicy(stream_idle_timeout=0.12))]
    finally:
        attempt_context.reset(token)
    assert stream.closed and stream.reader_cancelled
    assert events[0][0] == "model.slow"


def test_sync_watchdog_closes_blocked_stream():
    class HangingStream(Stream):
        closed_event = threading.Event()
        def __iter__(self):
            yield Obj(type="message_start")
            self.closed_event.wait(2)
        def close(self):
            self.closed_event.set()
            self.closed = True
    stream = HangingStream([])
    with pytest.raises(ModelTimeoutError):
        list(guarded_stream(stream, ModelRetryPolicy(stream_idle_timeout=0.05)))
    assert stream.closed


def test_heartbeats_do_not_reset_progress(monkeypatch):
    now = [0.]
    monkeypatch.setattr("hagent.model_retry.anthropic.time.monotonic", lambda: now[0])
    watchdog = StreamWatchdog(ModelRetryPolicy())
    watchdog.observe(Obj(type="message_start"))
    for second in range(10, 90, 10):
        now[0] = second
        watchdog.observe(Obj(type="ping"))
        watchdog.check()
    now[0] = 90
    with pytest.raises(ModelTimeoutError):
        watchdog.check()
    for delta in [Obj(text="文字"), Obj(thinking="思考"), Obj(partial_json='{"x":1}')]:
        watchdog.observe(Obj(type="content_block_delta", delta=delta))
        watchdog.check()
        now[0] += 89
        watchdog.check()
