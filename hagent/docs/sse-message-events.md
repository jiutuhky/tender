# hagent Agent SSE 消息事件手册

> 面向**前端 message 解析与渲染**。本手册穷举 `POST /sessions/{sid}/messages` SSE 流上的全部事件类型、`data` 字段形态、流式语义与渲染建议。
>
> 事实来源：
> - 服务端格式化与翻译：`hagent/src/hagent/server/sse.py`
> - SSE 端点与事件拦截：`hagent/src/hagent/server/routers/messages.py`
> - 子代理归属注入：`hagent/src/hagent/subagents/agent_tool.py`
> - 参考解析器（reducer）：`hagent/web/src/lib/chat_timeline.ts`、`frontend/lib/hagent/timeline.ts`
> - 契约测试：`hagent/tests/server/test_sse_adapter.py`、`test_sse_sandbox_events.py`

---

## 1. 传输层：SSE 帧格式

事件流由 `SSEFormatter.format(event, data)`（`sse.py`）产生，每帧三行 + 空行分隔：

```
id: <自增整数>
event: <事件名>
data: <JSON，单行，ensure_ascii=False>

```

- **`id`**：每条 SSE 流内从 `0` 单调自增（仅用于排序/去重参考，业务无依赖）。
- **`event`**：事件名，见第 2 节。
- **`data`**：永远是一个 JSON 对象（`error` 也是对象）。中文不转义（`ensure_ascii=False`），前端按 UTF-8 解码即可。
- **分隔符**：帧间以 `\n\n` 分隔。前端 `streamMessage`（`hagent_api.ts`）按 `\n\n` 切块，逐行解析 `id: ` / `event: ` / `data: ` 前缀，`data` 多行时拼接，最后 `JSON.parse`（失败则保留原始字符串）。

> ⚠️ `data` 行解析用的是固定前缀 `"data: "`（6 字符），与标准 SSE 一致。当前实现里每个事件的 `data` 都是单行 JSON，不会跨多行。

### 客户端拿到的标准化结构

```ts
interface SSEEvent {
  id: string;      // "0", "1", ...
  event: string;   // "message.delta" 等
  data: unknown;   // 已 JSON.parse 的对象
}
```

---

## 2. 事件总览

`POST /sessions/{sid}/messages` 流上会出现的事件（来自 `_stream_agent_events`）：

| 事件名 | 来源 | 频率 | 作用 |
|---|---|---|---|
| `message.delta` | LangGraph `messages` 流 | 高频 | 助手文本 / thinking 增量 token |
| `tool_call.started` | LangGraph `messages` 流 | 高频 | 工具调用名 + 入参分片（流式） |
| `tool_call.completed` | LangGraph `messages` 流 | 每个工具一次 | 工具执行结果 |
| `todo.updated` | 路由层拦截后合成 | 任务工具完成时 | 全量 Todo 列表快照 |
| `interrupt.requested` | LangGraph `updates` 流 | 偶发 | 智能体请求人工介入（HITL） |
| `run.started` | 消息路由层 | 每流一次 | 对话轮已登记为 `chat_turn` Run |
| `workspace.checkpointed` | 轮末 checkpoint 管道 | 有文件提交时一次 | 项目工作区成果已持久化到 host git |
| `done` | 流末尾 | 每流一次（正常） | 流正常结束 |
| `error` | 异常兜底 | 每流至多一次 | 智能体执行抛错 |

另有一组 **`sandbox.*` 生命周期事件**（`sandbox.created` / `paused` / `resumed` / `evicted` / `error`）已在 `sse.py` 定义并测试，但**当前尚未接入本消息流**（`render_sandbox_event` 无调用方）。见第 5 节，前端可预留处理但不应依赖其出现。

> ❗注意：`todo.refresh_requested` 是一个**内部事件**，由 `parse_lg_chunk` 产生后被路由层（`messages.py`）拦截，转而拉取全量 Todo 并发出 `todo.updated`。**它不会出现在 SSE 流上**，前端无需处理。

---

## 3. 子代理归属：`parent_tool_use_id`（核心机制）

`message.delta` / `tool_call.started` / `tool_call.completed` 三类事件的 `data` 都带 **`parent_tool_use_id`** 字段：

- **`null`** → 主 agent（顶层）产生的事件。
- **某个字符串** → 该事件由子代理产生，值等于**派发它的 `Agent` 工具调用的 `call_id`**。

机制（`agent_tool.py` 的 `_forward_config`）：`Agent` 工具把自己的 `tool_call_id` 注入子代理的 config `metadata.parent_tool_use_id`；子代理流式 token 的 metadata 随之携带该值；`sse.py` 把它挂到每个事件上。

**前端必须据此路由**，把子代理事件嵌入对应 `Agent` 调用节点下，**不要靠「最近一个 running 子代理」猜测**——并行多 Agent 下猜测会互相嵌套、串台、永不收尾。参考实现 `routeInto` / `mapChildrenOf`（`timeline.ts`）：`parent_tool_use_id` 为空挂顶层；否则在树中按 `call_id` 找到对应 subagent，挂到其 `children`；找不到则防御性落回顶层。

> `interrupt.requested` / `todo.updated` / `done` / `error` **不带** `parent_tool_use_id`。

---

## 4. 各事件 `data` 详解

### 4.1 `message.delta` — 文本 / thinking 增量

```ts
{
  role: "assistant",
  content_chunk: string | ContentBlock[],
  parent_tool_use_id: string | null
}
```

`content_chunk` 有两种形态，**前端两种都要处理**：

1. **`string`**：普通文本 token（多数模型 / 非 extended-thinking 路径）。
2. **`ContentBlock[]`**：Anthropic extended-thinking 模型返回的内容块数组，原样透传、不拼接、不过滤。块形态：

```ts
type ContentBlock =
  | { type: "thinking"; thinking: string }
  | { type: "text"; text: string }
  | { type: "redacted_thinking"; /* ... */ }   // 加密推理，无明文
  | { /* 其他未来块类型 */ };
```

渲染规则（参考 `appendContentDelta`）：
- `type === "thinking"` → 取 `block.thinking`，渲染进**思考块**（折叠区）。
- `type === "text"` → 取 `block.text`，渲染进**助手正文**。
- 其他类型（如 `redacted_thinking`）当前参考实现**忽略**；前端可按需提示「已隐藏的推理」。

**流式拼接**：同一连续段（thinking 或 text）的多个 delta 要**追加到上一条同类消息**，而非每个 token 新建气泡（见 `appendStreamChunk`：末条消息 role 相同则拼接 `content`）。空 `content_chunk` 应忽略。

> 即使某帧只含 thinking 块（无 text），也会照发 `message.delta`——前端应显示推理过程。

### 4.2 `tool_call.started` — 工具调用（流式入参）

```ts
{
  call_id: string | null,
  tool_name: string,           // 可能为 ""（仅在极早期分片，正常已被 state 回填）
  args_chunk: string,          // 入参 JSON 的一个分片，可能为 ""
  parent_tool_use_id: string | null
}
```

**流式语义（关键）**：一次工具调用会产生**多条** `tool_call.started`：
- 第一条通常带 `tool_name` 和 `call_id`，`args_chunk` 是入参 JSON 起始片段。
- 后续条目模型常只发 `args` 分片（原始 `name=None, id=None`）。但服务端用 `tool_call_state[index]` **回填** `call_id` 与 `tool_name`，所以前端拿到的这两个字段在同一调用内是稳定的（见 `test_parse_tool_call_args_chunks_without_repeated_name`）。
- 前端需**按 `call_id` 聚合**，把所有 `args_chunk` 顺序拼接成完整入参 JSON 字符串后再 `JSON.parse`（中途可能是不完整 JSON，渲染时容错）。

参考实现 `appendOrUpdateToolStarted`：同 `call_id` 已存在则 `args += args_chunk` 并补 `tool_name`；否则新建 `status:"running"` 的工具节点。

**特例：`tool_name === "Agent"`**（派发子代理）。不要当普通工具渲染，而要建一个 **subagent 节点**（`startToolInLevel`）。其入参 JSON 解析出：
```ts
{ description?: string, prompt?: string, subagent_type?: string | null }
```
`description` 作标题（缺省 "Subagent task"），`subagent_type` 缺省 `"general-purpose"`。该 subagent 的 `children` 由后续带 `parent_tool_use_id === 此 Agent call_id` 的事件填充。

### 4.3 `tool_call.completed` — 工具结果

```ts
{
  call_id: string | null,
  tool_name: string,
  result_summary: string,       // 工具结果全文，字符串化；名为 summary 但不截断
  parent_tool_use_id: string | null
}
```

- `result_summary` 是工具返回内容 `str(result)`，**完整不截断**（`test_parse_tool_message_preserves_full_result` 验证 1200 字符原样保留）。前端如需折叠请自行处理。
- 按 `call_id` 找到对应 running 工具节点，置 `status:"done"` 并填 `result`（`appendOrUpdateToolCompleted`）。若没有匹配的 started（理论边界），参考实现会补建一个 done 节点。
- **`Agent` 的完成**：同样以 `tool_call.completed` 到达，`call_id` = 该 Agent 调用 id。前端应收尾对应 subagent 节点（置 done、填 result），而非新建工具节点（`completeInLevel`）。

### 4.4 `todo.updated` — Todo 全量快照

```ts
{ todos: Todo[] }
```

由路由层在任务工具（`TaskCreate` / `TaskGet` / `TaskUpdate` / `TaskList`，见 `TASK_TOOL_NAMES`）完成后**主动拉取全量任务**合成发出（`messages.py`）。**全量替换**，非增量。

`Todo` 形态（`task_to_todo`）：
```ts
{
  id: string,
  content: string,        // = task.subject，列表显示文案
  status: "pending" | "in_progress" | "completed",
  description: string,
  blockedBy: string[],    // 阻塞它的任务 id
  owner?: string          // 仅当有 owner 时存在
}
```

前端处理：直接用 `data.todos` **替换**本地 todo 列表（参考 `workspace.ts`：`if (Array.isArray(d.todos)) todos = d.todos`）。该事件**不进** timeline reducer。

> 注意区分：`write_todos` 工具（deepagents 内置）完成时**不会**触发 `todo.updated`，只有上述四个 Task 工具会（`test_parse_write_todos_completion_does_not_emit_todo_events`）。

### 4.5 `interrupt.requested` — 人工介入请求（HITL）

```ts
{ payload: string }   // 中断状态的字符串化（str(state)），含完整 payload
```

来自 LangGraph `updates` 流的 `__interrupt__` 节点。`payload` 是字符串化的中断负载（`test_parse_interrupt_preserves_full_payload` 验证不截断）。

> 现状：后端 `/sessions/{sid}/interrupt` 端点（`InterruptBody: {interrupt_id, decision, reason?}`）为 **MVP 占位**，收到后返回 `{ok: true, session_id: <sid>, decision: <回显>}`，**不会真正 resume** 智能体。前端可展示中断意图，但恢复链路尚未打通。
>
> 注意：`decision` 在后端为任意 `str`（**不做枚举校验**，`messages.py:166`）；`approve|reject|edit|respond` 只是前端 `postInterrupt`（`hagent_api.ts`）的约定取值，并非后端契约。

### 4.6 `run.started` — Run 已开始

```ts
{ run_id: string }
```

每条实际进入 Agent 执行的消息都会先登记一个 `kind=chat_turn` 的 Run，并在 Agent 输出前发出该事件。被 `UserPromptSubmit` hook 阻断、未进入执行的消息不创建 Run。

### 4.7 `workspace.checkpointed` — 工作区已持久化

```ts
{
  run_id: string,
  commit_sha: string,
  files_changed: string[]
}
```

当本轮产生文件变化时，服务端会在流结束前把 guest 变更回写项目 canonical workspace、形成 host git commit，再发出该事件。正常路径的顺序固定为 `run.started` → Agent 增量事件 → `workspace.checkpointed` → `done`。无文件变化的轮次是 no-op，不发 `workspace.checkpointed`；异常路径会尽力 checkpoint，成功时该事件出现在 `error` 前。

### 4.8 `done` — 流正常结束

```ts
{ thread_id: string }   // = session id
```

流的最后一帧（正常路径）。前端据此切换阶段（如 `phase: "done"`）、停止 loading 态。

> 前端注意缓冲冲刷：若用 rAF 批处理事件（如 `workspace.ts` 的 `pushEvent`/`flushEvents`），流结束时必须 `flushEvents()` 落地末帧，避免 `done` 前的尾部事件被丢在 buffer。

### 4.9 `error` — 执行异常

```ts
{
  code: "agent_error" | "workspace_checkpoint_error",
  message: string
}
```

- `agent_error`：`agent.stream` 抛异常时的兜底帧（`message = str(e)`）。服务端会先 best-effort checkpoint，成功时先发 `workspace.checkpointed`。
- `workspace_checkpoint_error`：Agent 已正常结束，但轮末持久化未完整收尾。若 host commit 已成功，仍会先发带真实 `files_changed` 的 `workspace.checkpointed`，随后用此错误提示 guest 基线或租约元数据需要下一轮追平。

出现 `error` 后流即终止（不会再有 `done`）。前端追加一条错误消息（参考 reducer：`role:"error"`）。

---

## 5. `sandbox.*` 生命周期事件（已接入：消息流开始时冲刷积压）

`sse.py` 的 `render_sandbox_event` / `SandboxEvent` 定义了沙箱生命周期事件，**格式与主流不同**：

```
event: sandbox.<kind>
data: {"event":"sandbox.<kind>","session_id":"...","sandbox_id":"..."|null,"reason":"..."|null}

```

- `kind ∈ {created, adopted, paused, resumed, evicted, orphaned, health_fail, snapshotted, restored, error}`。
- **无 `id:` 行**（不经 `SSEFormatter`）。
- `data` 里有冗余的 `event` 字段（与 `event:` 行同值）。
- `error` 类型的 `reason` 携带原因（如 `"image_pull_failed"`）。
- `snapshotted`（Task C2）：沙箱 idle 超阈值被休眠到 DISK 快照，VM 已拆除、会话数据保留；下一条消息会触发恢复。`restored`：从快照恢复完成（新 VM 已就绪）。

**接入方式（Task B7 起）**：sandbox 事件发生在后台线程（supervisor / 池 GC / reconciler），先积压在会话级队列（每会话上限 50，溢出丢最旧）；`POST /messages` 的 SSE 流在 agent 输出**之前**冲刷积压事件。也就是说：事件不实时推送，只随下一次消息交互到达；前端处理分支应容忍乱序与缺失（事件表 `sandbox_events` 是完整历史的事实源）。注意它与主流事件 `data` 结构不一致（自带 `event` 键、无自增 `id`）。

---

## 6. 配套 HTTP 接口（非 SSE，但前端必备）

除消息流外，前端还会用到以下普通 HTTP 接口（`messages.py`）：

### `GET /sessions/{sid}/messages` — 历史消息回放

会话恢复时拉取全部历史消息，返回 `Array<{ role, content }>`（`_normalize_message`）：
- **`role` 取自 LangGraph `BaseMessage.type`，取值 `ai | human | tool | system`**——**与 SSE 流里 `message.delta` 固定的 `"assistant"` 不同**，前端回放时需自行映射（`ai`→助手、`human`→用户、`tool`→工具结果）。
- `content` 同样可能是 `string | ContentBlock[]`，按第 4.1 节规则渲染。

### `GET /sessions/{sid}/todos` — Todo 冷启动 / 刷新

返回与 `todo.updated` **同形态**的 `Todo[]`（走同一 `_task_store_todos`）。SSE 只在任务工具完成时推送；首次进入或手动刷新时用此接口拉全量。

### Composer 输入语法糖：`/skill:<name> [args]`

发送的 `content` 若以 `/skill:` 开头，服务端 `_expand_skill_message` 会改写成「Use the `Skill` tool with skill: "<name>" …」。前端 Composer 可直接透传此语法，无需自行展开。

---

## 7. 前端实现清单（落地建议）

1. **解码**：按 `\n\n` 切帧 → 解析 `id`/`event`/`data` → `JSON.parse(data)`。已有 `streamMessage` 封装。
2. **timeline reducer**：处理 `message.delta`、`tool_call.started`、`tool_call.completed`、`error`，按 `parent_tool_use_id` 路由层级。直接复用 `frontend/lib/hagent/timeline.ts` 的 `reduceChatEvent`（纯函数）。
3. **Todo 面板**：单独处理 `todo.updated`，全量替换，不进 timeline。
4. **阶段控制**：`done` → 完成；`error` → 错误态；二者互斥。
5. **画布产物**：矩阵画布数据走对象库 REST 端点（`/projects/{pid}/matrices/**`），不再扫 workspace 文件。解析期间槽位状态由 `prose_*` 工具事件推导：`prose_submit_matrix_records` 的 `tool_call.started` 翻「解析中」，`prose_publish_matrix` 的 `tool_call.completed` 触发 REST 装载点亮，流结束后全量对账兜事件缺漏（参考实现 `frontend/lib/store/workspace.ts`）。`workspace.checkpointed` 不再触发画布刷新，仅表示文件成果已持久化到 host git；`run.started` 可记录当前 `run_id`。
6. **HITL**：`interrupt.requested` 可视化（恢复链路待后端打通）。
7. **聚合**：工具入参按 `call_id` 拼 `args_chunk`；文本/thinking 增量按连续同类追加。
8. **子代理**：`Agent` 工具 → subagent 节点；其内部事件靠 `parent_tool_use_id` 归属。
9. **容错**：`call_id` 可能为 `null`、入参 JSON 中途不完整、`content_chunk` 两种形态、未知 block.type，均需不崩。

---

## 8. 典型事件序列（示意）

```
event: tool_call.started      data: {call_id:"a1", tool_name:"Agent", args_chunk:"{\"desc", parent_tool_use_id:null}
event: tool_call.started      data: {call_id:"a1", tool_name:"Agent", args_chunk:"ription\":\"解析\"}", parent_tool_use_id:null}
  event: message.delta        data: {role:"assistant", content_chunk:[{type:"thinking",thinking:"先看文件…"}], parent_tool_use_id:"a1"}
  event: tool_call.started    data: {call_id:"r1", tool_name:"Read", args_chunk:"{\"path\":\"x.md\"}", parent_tool_use_id:"a1"}
  event: tool_call.completed  data: {call_id:"r1", tool_name:"Read", result_summary:"……", parent_tool_use_id:"a1"}
  event: message.delta        data: {role:"assistant", content_chunk:"解析完成", parent_tool_use_id:"a1"}
event: tool_call.completed    data: {call_id:"a1", tool_name:"Agent", result_summary:"子代理产出…", parent_tool_use_id:null}
event: tool_call.completed    data: {call_id:"t9", tool_name:"TaskUpdate", result_summary:"Updated task 1", parent_tool_use_id:null}
event: todo.updated           data: {todos:[{id:"1",content:"…",status:"completed",description:"…",blockedBy:[]}]}
event: message.delta          data: {role:"assistant", content_chunk:"全部完成。", parent_tool_use_id:null}
event: done                   data: {thread_id:"<sid>"}
```

（缩进仅示意 `parent_tool_use_id` 归属层级；实际流是平铺的，无缩进。）
