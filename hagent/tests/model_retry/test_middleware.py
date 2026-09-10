import asyncio
from types import SimpleNamespace

import pytest

from hagent.model_retry.middleware import ModelRetryMiddleware
from hagent.model_retry.policy import ModelCallFailed, ModelRetryPolicy, ModelRunCancelled
from hagent.model_retry.runtime import RunControl, run_control
from hagent.tool_error_guard import ToolErrorGuardMiddleware
from tests.model_retry.test_policy import api_error


@pytest.fixture
def setup(monkeypatch):
    events = []
    context = {"model_call_id": "call-1", "run_id": "run-1", "parent_tool_use_id": "parent-1"}
    monkeypatch.setattr("hagent.model_retry.middleware.call_context", lambda: (context, lambda event, data: events.append((event, data))))
    monkeypatch.setattr("hagent.model_retry.middleware.adapt_model", lambda model, policy, data: data)
    request = SimpleNamespace(model=None, override=lambda **kwargs: SimpleNamespace(**kwargs))
    sleeps = []
    monkeypatch.setattr(RunControl, "sleep", lambda self, delay: sleeps.append(delay))
    async def asleep(self, delay):
        sleeps.append(delay)
    monkeypatch.setattr(RunControl, "asleep", asleep)
    return events, request, sleeps


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.asyncio
async def test_exact_budget_sync_async(setup, asynchronous):
    events, request, sleeps = setup
    calls = []
    def handler(request):
        calls.append(request.model["attempt"])
        raise ConnectionError("EOF")
    async def ahandler(request):
        return handler(request)
    middleware = ModelRetryMiddleware(ModelRetryPolicy())
    with pytest.raises(ModelCallFailed) as error:
        if asynchronous:
            await middleware.awrap_model_call(request, ahandler)
        else:
            middleware.wrap_model_call(request, handler)
    assert calls == list(range(1, 12))
    assert len(sleeps) == 10
    assert error.value.attempts == 11
    assert sum(e == "model.retry" for e, _ in events) == 10
    assert {d["model_call_id"] for _, d in events} == {"call-1"}


@pytest.mark.asyncio
async def test_success_resets_budget_and_permanent_fails_fast(setup):
    events, request, sleeps = setup
    calls = 0
    async def handler(request):
        nonlocal calls
        calls += 1
        if calls % 2:
            raise ConnectionError()
        return "完整回复"
    middleware = ModelRetryMiddleware(ModelRetryPolicy(max_retries=1))
    assert await middleware.awrap_model_call(request, handler) == "完整回复"
    assert await middleware.awrap_model_call(request, handler) == "完整回复"
    assert len(sleeps) == 2
    async def permanent(request):
        raise api_error(500, {"code": "convert_request_failed"})
    with pytest.raises(ModelCallFailed) as error:
        await middleware.awrap_model_call(request, permanent)
    assert error.value.attempts == 1
    assert error.value.info.category == "protocol"


@pytest.mark.asyncio
async def test_cancel_backoff():
    control = RunControl()
    task = asyncio.create_task(control.asleep(3600))
    await asyncio.sleep(0)
    control.cancel()
    with pytest.raises(ModelRunCancelled):
        await asyncio.wait_for(task, 0.3)


@pytest.mark.asyncio
async def test_fatal_child_bypasses_tool_guard():
    failure = ModelCallFailed(__import__('hagent.model_retry.policy', fromlist=['classify_error']).classify_error(ConnectionError()), 11, {})
    guard = ToolErrorGuardMiddleware()
    def handler(_):
        raise failure
    async def ahandler(_):
        raise failure
    with pytest.raises(ModelCallFailed):
        guard.wrap_tool_call(None, handler)
    with pytest.raises(ModelCallFailed):
        await guard.awrap_tool_call(None, ahandler)


def test_empty_complete_envelope_is_not_a_success():
    from langchain_core.messages import AIMessage
    from hagent.model_retry.policy import IncompleteResponseError
    with pytest.raises(IncompleteResponseError):
        ModelRetryMiddleware._validate(SimpleNamespace(result=[AIMessage(content="")]))
