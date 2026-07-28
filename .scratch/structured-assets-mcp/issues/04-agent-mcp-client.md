# 04 hagent agent 接入 MCP client

Status: resolved
Type: task
Blocked by: 03

## Parent

`.scratch/structured-assets-mcp/PRD.md`（契约：hagent spec §6）

## What to build

hagent 主 agent（及 subagent worker）以真 MCP client 获得 `prose_*` 工具：server 模式 loopback 连 `/mcp`，CLI host 模式经 stdio 拉起同一 FastMCP 对象。接入点在 `create_hagent()` 组装线。**动工前必读**：仓内 `deepagents/mcp.mdx` 指向的官方文档 + langchain-mcp-adapters 实际 API（以 `.venv` 源码为准，勿猜 API——CLAUDE.md 既有纪律）。

## Acceptance criteria

- [x] server 模式：session 内 agent 可见并可调 `prose_*` 工具，SSE 流中工具调用事件正常呈现（前端 08 票依赖此事件名）（真 uvicorn loopback 测试锁 15 个工具名并真调；SSE 层以 `parse_lg_chunk` 单测锁 `tool_call.started/completed` 按名透传——真实模型全链呈现留给门控 e2e）
- [x] CLI host 模式：`python -m hagent demo` 链路下同一工具面可用（stdio 子进程共享 SQLite/WAL）（`run_demo` 接线测试 + stdio 真调回环：子进程写、宿主进程 SQLite 直读断言）
- [x] subagent（extraction worker）继承工具面，四路并发提交不同矩阵草稿无相互干扰（继承走 `compile_subagents(parent_tools=...)` 结构断言；四线程并发对四矩阵 start+submit+query 互不串扰——工具层直调，未过真实 worker/模型）
- [x] sandbox 模式回归：MCP 工具在宿主执行不受沙箱切线影响，`pytest tests/server -v` 全绿（fake sandbox 下 15 工具在池且 stdio 真调成功；tests/server 216 passed, 1 skipped）
- [x] 工具面唯一性成立：agent 侧无任何绕过 MCP 的原生资产写工具（`test_no_native_asset_write_bypass`：资产语义工具名集合 == 15 个 `prose_*`）

## Comments

2026-07-13（实现，agent）：agent 侧 client 落地为 `hagent/src/hagent/mcp_tools.py`（连接构造 + `load_prose_mcp_tools`），run 归属层 `hagent/src/hagent/assets/mcp_actor.py`；接线点 `core.py`（`create_hagent(mcp_connection=...)`，工具进 parent_tools 故 subagent 自动继承）、`server/agents.py`（loopback HTTP，actor=`session:<sid>`）、`cli.py`（stdio，actor=`cli-demo`）。新依赖 `langchain-mcp-adapters>=0.3`。测试 `tests/test_mcp_tools_wiring.py`（11）+ `tests/server/test_mcp_agent_loopback.py`（4，含真 uvicorn 临时端口）+ 共享件 `tests/prose_mcp.py`，全仓 1137 passed。实现期决策（已回写 spec §6「实现期定案（票 04 回写）」）：

- **sync 桥**：deepagents graph 在 server（threadpool 里 `agent.stream`）与 CLI（`agent.invoke`）都同步执行，adapter 工具只有 coroutine——模块持一条后台事件循环 daemon 线程，给每个工具补阻塞式 `func`（async 路径原样保留）。server 模式无自锁：调用方在 worker 线程阻塞，主事件循环仍可服务 `/mcp`（真 uvicorn 测试验证）。
- **每次调用新建 MCP session**（adapter 默认）：stateless server + 状态只在 DB 天然匹配，无连接生命周期要管；stdio 侧代价是每次工具调用 ~1s 子进程启动，demo 量级可接受，慢了再换持久 session。
- **run 归属**：HTTP 经 `X-Hagent-Actor-Ref` header → `ActorRefASGI` 收进 ContextVar（stateless FastMCP 工具任务从请求任务派生，contextvars 随任务复制——经真 uvicorn 审计断言验证）；stdio 经子进程 env。粒度为 session（agent 按 session 缓存，header 随连接固定），非 spec §2 示例的 run 粒度——per-run 需每条消息重建工具面，不值。
- **loopback URL**：`HAGENT_MCP_URL` → 默认 `http://127.0.0.1:8000/mcp`（README 规范端口）；app 无法自知 bind 端口，非默认端口部署必须设 env，加载 fail-loud 兜错配。**进程内 ASGI 直连被否**：stateless FastMCP 的请求任务挂在 lifespan task group（loop-bound），跨事件循环调用会炸——这也是 server 测试用真 uvicorn 临时端口的原因。
- **stdio 子进程 env 白名单**（PATH/HOME + DB/workspace/skills + actor ref，API key 不透传），对齐 `inherit_env=False` 纪律；`HAGENT_MCP_DISABLED` 为 server/CLI 两个装配点共同关断阀。

双轴评审（Standards + Spec 并行子代理）结论：无实质缺陷。已修：测试共享件去重（`tests/prose_mcp.py`）、SSE 事件名单测补 AC1、core.py import 顺序。**接受不改**的判断项：两装配点重复 `None if disabled else connection` 形状（关断折进构造器会让「构造连接」语义变脏，第三装配点出现时再收）；`mcp_connection` 用 `dict[str, Any]` 不引 adapter 的 `Connection` 类型进 core 签名（运行时同为 dict，docstring 已注明类型）；`DEFAULT_MCP_URL` 硬编码为已文档化取舍。评审同时指出工作区混着 sanitize 中间件搬移等**票外 WIP**——本票提交以 hunk 级拆分排除，不带入。
