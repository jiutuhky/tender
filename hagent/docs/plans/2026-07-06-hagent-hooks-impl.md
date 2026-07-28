# Plan: Hagent Hooks 实现任务分解

**Spec**: `docs/specs/2026-07-06-hagent-hooks-design.md`
**Date**: 2026-07-06

每个 Task 一个 commit（Conventional Commits），TDD：先写失败测试再实现。

## Phase 0 — 纯逻辑层（不动现有文件）

- **Task 0.1** `hooks/context.py` + `hooks/events.py`：HookContext/base_payload、HookEvent 27 枚举、build_payload、match_query_for、事件默认超时表。测试：`tests/hooks/test_events.py`（payload 拼写快照，逐字段对齐 coreSchemas.ts）。
- **Task 0.2** `hooks/schema.py`：Command/Prompt/Agent/Http 四型 discriminated union（`if`/`async`/`continue` alias）、HookJSONOutput、HookSpecificOutput。测试：`tests/hooks/test_schema.py`。
- **Task 0.3** `hooks/matcher.py`：matches_pattern（空/`*`/简单串 `|` 精确/正则/非法正则回退）。测试：`tests/hooks/test_matcher.py` 表驱动。
- **Task 0.4** `hooks/config.py`：三层 settings 发现合并、去重（后合并 scope 胜出）、`HAGENT_HOOKS_DISABLED` / `HAGENT_HOOKS_SETTINGS_PATHS` / `HAGENT_HOOKS_READ_CLAUDE_SETTINGS`、未支持事件 warning。测试：`tests/hooks/test_config.py`。

## Phase 1 — 执行层

- **Task 1.1** `hooks/executor.py` command 型：asyncio subprocess、stdin JSON+`\n`、超时 killpg、exit code 三态、JSON 输出解析。测试：`tests/hooks/test_executor.py`（真子进程 fake hook）。
- **Task 1.2** `hooks/executor_http.py`：httpx POST、600s 默认、空 body=`{}`。测试 monkeypatch httpx。
- **Task 1.3** `hooks/executor_llm.py`：prompt 型（$ARGUMENTS 替换、ok 判定、30s）+ agent 型（只读工具 verifier、60s、限轮次）。测试 monkeypatch 模型。
- **Task 1.4** `hooks/runner.py`：匹配→once 过滤→gather 并行→HookAggregate 聚合（deny>ask>allow、blocked、contexts）；`has_hooks` O(1)；sync 桥。测试：并行计时断言、聚合优先级、once。

## Phase 2 — 图内接线

- **Task 2.1** `hooks/middleware.py`：wrap_tool_call/awrap_tool_call（PreToolUse deny 短路/ask 降级/updatedInput override/PostToolUse(Failure) context 追加）+ after_model/aafter_model（Stop + jump_to + 双保险）。全部 sync+async 双实现 + 反射测试断言成对覆写。测试：直调层 `tests/hooks/test_middleware.py`。
- **Task 2.2** 真图集成测试 `tests/hooks/test_middleware_graph.py`：`langchain.agents.create_agent` + FakeToolCallingModel + 真 hook 脚本，断言 deny 短路、Stop 阻断后回 model、二次 payload `stop_hook_active=true`。
- **Task 2.3** `core.py` 装配：`create_hagent(hook_runner=...)`、无配置零开销、middleware 头部注入、`_hagent_hook_runner` 属性；`HagentConfig` 增 hooks 字段。测试：`tests/test_core.py` 增（monkeypatch `_create_deep_agent` 断言注入）。

## Phase 3 — server 接线

- **Task 3.1** `server/hooks_registry.py`：per-session HookRunner + pending_session_context；`agents.py` 装配复用。
- **Task 3.2** `routers/messages.py` UserPromptSubmit：blocked → `hook.blocked` SSE + done、不进图；contexts/pending 注入。`sse.py` 增事件。
- **Task 3.3** `routers/sessions.py` SessionStart/SessionEnd：create 后触发（blocking 忽略、initialUserMessage 入响应体）、delete 前触发（1.5s）。
- **Task 3.4** server e2e `tests/server/test_hooks_server.py`。

## Phase 4 — P1

- **Task 4.1** [DONE] SubagentStart/SubagentStop：`subagents/loader.py` 释放 frontmatter `hooks`；Stop→SubagentStop 自动转换在 `hooks/config.py load_hooks_dict`；`compiler.py` 注入子代理专属 middleware（stop_event=SubagentStop）；`agent_tool.py` 触发 SubagentStart。
- **Task 4.2** [DONE·部分] PermissionDenied：PreToolUse hook deny 短路处触发；bash 工具内部 deny 分支未接（bash_tool 无 runner 通路，后续再议）。
- **Task 4.3** [TODO] Notification（permission_request 型起步）+ systemMessage → SSE。
- **Task 4.4** [DONE] transcript 简版 JSONL（`server/transcript.py`，messages 路由旁路追加 user/assistant）。
- **Task 4.5** [TODO] HITL ask（deepagents `interrupt_on` + `/interrupt` 端点接通）；当前 ask 降级为 deny。

## 验收

1. `pytest -v` 全绿（无外部 key）。
2. 手工 e2e：`.hagent/settings.json` 配 PreToolUse deny（matcher=Bash）+ Stop exit 2 脚本，起 server 建 session 发消息，SSE 观察工具被拒 + Stop 阻断一轮后正常结束。
3. `set -a && source .env && set +a && pytest tests/test_demo_e2e.py -v -s`（真实模型门控，middleware 不破坏既有链路）。
