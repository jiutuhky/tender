# Design Spec: Hagent Hooks（Claude Code hook 机制移植）

**Date**: 2026-07-06
**Repo**: `/home/han/workplace/tender`（`hagent/` 子目录）
**Status**: APPROVED
**对齐基准**: `hagent/docs/cc-recovered-main`（CC 2.1.88 恢复源码）

## 1. Problem Statement

hagent 目前没有任何 hook 机制：用户无法在工具调用前后、prompt 提交、会话生命周期、agent 停止等时机注入外部命令做治理（阻断危险操作、注入上下文、驱动 CI 校验等）。目标是把 Claude Code 的 hook 能力移植到 hagent，**行为与 CC 一致**：事件名、stdin payload 字段拼写、exit code 语义（0/2/其他）、默认超时（工具类 600s、SessionEnd 1.5s、prompt 30s、agent 60s、http 600s）、matcher 匹配逻辑、JSON 高级控制字段逐一对齐。

CC 侧权威参照：

- 事件与 payload：`docs/cc-recovered-main/src/entrypoints/sdk/coreSchemas.ts:355-765`
- 执行引擎：`docs/cc-recovered-main/src/utils/hooks.ts`（matchesPattern:1346 / getMatchingHooks:1603 / execCommandHook:747 / executeHooks:1952 / processHookJSONOutput:489）
- 消费端：`src/services/tools/toolHooks.ts`、`src/query/stopHooks.ts`、`src/utils/processUserInput/processUserInput.ts`、`src/utils/sessionStart.ts`
- prompt/agent/http 执行器：`src/utils/hooks/exec{Prompt,Agent,Http}Hook.ts`
- 配置 schema：`src/schemas/hooks.ts`

## 2. Scope

**范围决策（用户已确认）**：

1. 事件核心集优先分阶段；`HookEvent` 枚举预留 CC 全部 27 个事件名，未实现事件出现在配置中时 warning「已识别未支持」。
2. hook 类型 **command / prompt / agent / http 四种全做**。
3. 配置走 `.hagent` 体系（`~/.hagent/settings.json` → `<project_root>/.hagent/settings.json` → `<project_root>/.hagent/settings.local.json`，后者优先）；schema 与 CC settings.json 的 `hooks` 字段同构。`HAGENT_HOOKS_READ_CLAUDE_SETTINGS=1` 可选读 `.claude/settings.json`（最低优先级），默认关。
4. PreToolUse 的 `permissionDecision:"ask"` 首期降级为 deny（reason 注明）；LangGraph interrupt/HITL 接通为 P1。

**事件分层**：

- P0：PreToolUse、PostToolUse、PostToolUseFailure、UserPromptSubmit、SessionStart、SessionEnd、Stop
- P1：SubagentStart、SubagentStop（含 frontmatter hooks + Stop→SubagentStop 自动转换）、PermissionDenied、Notification、PermissionRequest（依赖 HITL）
- 不做：PreCompact/PostCompact（hagent 禁用 SummarizationMiddleware，无 compaction 事件源）；TeammateIdle/TaskCreated/TaskCompleted（CC team 子系统）；Elicitation/ElicitationResult（MCP elicitation UI）；CwdChanged/FileChanged/Worktree*/InstructionsLoaded/ConfigChange/Setup/StopFailure（绑定 CC 本地 CLI 形态，hagent 无触发源）
- `async:true` 做 fire-and-forget；`asyncRewake` 不做（SSE 会话无 rewake 通道）

## 3. Architecture

新包 `src/hagent/hooks/`：

```text
src/hagent/hooks/
  __init__.py       # HookRunner / HagentHooksMiddleware / load_hook_settings
  context.py        # HookContext + base_payload()（session_id/transcript_path/cwd/...）
  events.py         # HookEvent(27) + build_payload() + match_query_for() + 事件默认超时
  schema.py         # pydantic v2：四型 HookConfig union + HookJSONOutput/HookSpecificOutput
  matcher.py        # matches_pattern()（CC hooks.ts:1346 对齐）
  config.py         # 三层 settings 发现/合并/去重 + env 覆盖
  executor.py       # command 型（asyncio subprocess，stdin JSON+\n，killpg 超时）
  executor_http.py  # http 型（httpx POST）
  executor_llm.py   # prompt 型（单次小模型求值）+ agent 型（只读工具 agentic verifier）
  runner.py         # 匹配→并行执行→HookAggregate 聚合（deny>ask>allow）
  middleware.py     # HagentHooksMiddleware：wrap_tool_call/awrap_tool_call
                    #   + after_model/aafter_model（@hook_config(can_jump_to=["model"])）
```

接线点：

- 工具三事件：`core.py` middleware 列表头部注入（最外层）；deny 短路 = 不调 handler 直接返回 error ToolMessage；updatedInput = `request.override(tool_call=...)`；additionalContext 以 `<system-reminder>` 追加到 ToolMessage 尾部（LangGraph 无 attachment 通道，模型可见性与 CC 等价，形态差异记录在案）。
- Stop：`after_model` 检测「无 tool_calls 的 AIMessage」，blocked 时返回 `{"messages":[HumanMessage(reason)], "jump_to":"model", ...}`；`stop_hook_active` payload 字段 + `hagent_stop_block_count` 硬上限（5）双保险防死循环。
- UserPromptSubmit：`server/routers/messages.py:post_message` 在进图前执行；blocked 时 prompt 不进 checkpointer（即 CC 的「擦除」），SSE 返回 `hook.blocked` + `done`。
- SessionStart/SessionEnd：`server/routers/sessions.py` create/delete；per-session `HookRunner` 缓存在 `server/hooks_registry.py`，与 `get_or_build_agent` 共用一实例（once 状态全 session 唯一）。SessionStart blocking 忽略（CC 语义），additionalContext 暂存至首条消息注入，initialUserMessage 随 create 响应返回。SessionEnd 默认 1.5s 超时、输出全忽略。

## 4. 行为契约（与 CC 逐项对齐）

- stdin：`json.dumps(payload, ensure_ascii=False) + "\n"`（尾随换行是 CC 刻意行为）。
- exit code：0=success（stdout 整体 JSON → HookJSONOutput，否则纯文本按事件语义）；2=blocking（stderr 为阻断消息，JSON reason 优先）；其他=non-blocking error。
- 并行：命中 hook 全部 `asyncio.gather` 并发，单个失败不影响其他。
- 权限优先级 deny > ask > allow；`updatedInput` 仅 allow/ask/passthrough 透传；hook allow 不绕过 hagent 自身工具权限（`evaluate_bash_permission`/`ensure_allowed` 继续生效）。
- `hookSpecificOutput.hookEventName` 与期望事件不符时丢弃并报错（CC processHookJSONOutput 同款）。
- 环境变量：`CLAUDE_PROJECT_DIR`（= server 进程 CWD 的项目根）。
- sandbox 模式：hook 在**宿主**执行（CC 同款语义——hook 是用户机器上的命令）；`tool_input` 内是容器内路径，文档给出映射说明。

## 5. 已知差异（记录在案）

1. `if` 条件首期不求值（恒真 + 加载 warning），仅参与去重 key。
2. `transcript_path` 指向 `/tmp/hagent/transcripts/<sid>.jsonl`，P0 阶段文件可能不存在（hagent 无 CC transcript），P1 补简版 JSONL。
3. P0 阶段子代理内工具调用不触发 hook（middleware 不进子图），P1 在 `subagents/compiler.py` 注入子代理专属 middleware 补齐。
4. additionalContext 的注入形态是 ToolMessage 尾部 `<system-reminder>`，而非 CC 的独立 attachment 消息。
5. `asyncRewake` 不支持。

## 6. Testing

- payload 字段拼写快照测试 = 「与 CC 行为一致」的守护线（逐字段对齐 coreSchemas.ts）。
- matcher / config 合并去重 / schema alias 单测；executor 用内联 bash fake hook（含超时杀进程组、stdin 回显断言）；middleware 直调层 + `create_agent` 真图层（验证 jump_to 真实语义）；server e2e 用 TestClient + 桩 agent。
- 全量门禁 `pytest -v` 不需要外部 API key。
