"""prompt / agent 型 hook 测试 —— fake 模型注入。"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import AIMessage

from hagent.hooks.events import HookEvent
from hagent.hooks.executor_llm import (
    execute_agent_hook,
    execute_prompt_hook,
    substitute_arguments,
)
from hagent.hooks.schema import AgentHookConfig, PromptHookConfig


class _FakeModel:
    """最小 fake：ainvoke 返回固定 AIMessage，记录收到的消息。"""

    def __init__(self, reply: str, delay: float = 0.0):
        self.reply = reply
        self.delay = delay
        self.calls: list[Any] = []

    async def ainvoke(self, messages, **kwargs):
        self.calls.append(messages)
        if self.delay:
            await asyncio.sleep(self.delay)
        return AIMessage(content=self.reply)


def test_substitute_arguments():
    assert substitute_arguments("check $ARGUMENTS now", "{}") == "check {} now"
    # 无占位则追加（对齐 CC substituteArguments appendIfNoPlaceholder）
    assert substitute_arguments("verify tests", '{"a":1}') == 'verify tests\n\n{"a":1}'


async def test_prompt_hook_ok_true():
    model = _FakeModel('{"ok": true}')
    res = await execute_prompt_hook(
        PromptHookConfig(prompt="did tests pass? $ARGUMENTS"),
        '{"x":1}',
        HookEvent.STOP,
        model_factory=lambda m: model,
    )
    assert res.outcome == "success"
    # $ARGUMENTS 已替换进用户消息
    user_msg = model.calls[0][1]
    assert '{"x":1}' in user_msg["content"]


async def test_prompt_hook_ok_false_blocks():
    res = await execute_prompt_hook(
        PromptHookConfig(prompt="verify"),
        "{}",
        HookEvent.STOP,
        model_factory=lambda m: _FakeModel('{"ok": false, "reason": "测试没跑"}'),
    )
    assert res.outcome == "blocking"
    assert res.prevent_continuation is True
    assert res.stop_reason == "测试没跑"
    assert "测试没跑" in (res.blocking_error or "")


async def test_prompt_hook_bad_json_non_blocking():
    res = await execute_prompt_hook(
        PromptHookConfig(prompt="verify"),
        "{}",
        HookEvent.STOP,
        model_factory=lambda m: _FakeModel("I think it's fine"),
    )
    assert res.outcome == "non_blocking_error"


async def test_prompt_hook_json_in_prose_extracted():
    res = await execute_prompt_hook(
        PromptHookConfig(prompt="verify"),
        "{}",
        HookEvent.STOP,
        model_factory=lambda m: _FakeModel('结论：{"ok": true} 完毕'),
    )
    assert res.outcome == "success"


async def test_prompt_hook_timeout_cancelled():
    res = await execute_prompt_hook(
        PromptHookConfig(prompt="verify", timeout=0.05),
        "{}",
        HookEvent.STOP,
        model_factory=lambda m: _FakeModel('{"ok": true}', delay=1.0),
    )
    assert res.outcome == "cancelled"


async def test_prompt_hook_model_error_non_blocking():
    def _factory(m):
        raise RuntimeError("no api key")

    res = await execute_prompt_hook(
        PromptHookConfig(prompt="verify"),
        "{}",
        HookEvent.STOP,
        model_factory=_factory,
    )
    assert res.outcome == "non_blocking_error"


async def test_agent_hook_verdict_from_final_message(monkeypatch):
    # 打桩 create_agent：返回一个 ainvoke 出 {"ok": false} 终态的假图
    class _FakeGraph:
        async def ainvoke(self, state, config=None):
            return {"messages": [AIMessage(content='{"ok": false, "reason": "缺测试"}')]}

    import langchain.agents as la

    monkeypatch.setattr(la, "create_agent", lambda **kw: _FakeGraph())
    res = await execute_agent_hook(
        AgentHookConfig(prompt="verify build"),
        "{}",
        HookEvent.STOP,
        tools=[],
        model_factory=lambda m: _FakeModel("unused"),
    )
    assert res.outcome == "blocking"
    assert res.stop_reason == "缺测试"
