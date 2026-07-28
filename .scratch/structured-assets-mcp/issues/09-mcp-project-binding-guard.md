# 09 MCP 面 project 绑定与存在性护栏(事后票)

Status: resolved
Type: task
Blocked by: 03, 04

> 事故驱动的事后补票:修复已随 commit `0ad161e` 落地(2026-07-14),本票为归档,
> 补齐 issue-tracker 票据链(验收审查发现该提交无对应票)。

## Parent

`.scratch/structured-assets-mcp/PRD.md`(契约:hagent spec §5/§6 工具面与安全边界)

## 事故(2026-07-13 前端实测)

agent 无从得知自己的 hagent project_id(sandbox 里 workspace 就是 `/workspace`),
于是把招标文件正文里的「项目编号:2025-JQ04-F1054」当 project_id 传给全部
`prose_*` 工具。只读与草稿类工具照单全收(对象库按 project_id 建命名空间、读时
不存在即返空),坐实错误判断;唯独碰文件系统的 `prose_register_document` 报
`file_not_found`——agent 用 Bash 明明看得见那个文件,陷入无法自解的矛盾,flail
60 余次工具调用(扫宿主端口、试图 POST /projects 造幽灵项目、开 ssh 反向隧道、
裸 vsock 捅 guest-agent)直至沙箱被健康巡检杀掉,前端显示 Sandbox not running。
对象库亦被写脏一个幽灵命名空间。

## What to build

两道护栏,挂在 tool 装配处,新增工具自动继承:

- **project 绑定**:server 按 session 把 project_id 打进 MCP 连接 header
  (`X-Hagent-Project-Id`,stdio 走 `HAGENT_MCP_PROJECT_ID` env),工具侧据此拒绝
  越界调用;错误 hint 携带正确 project_id,agent 一个来回即自愈。agent 自报的
  project_id 不再被信任。
- **存在性校验**:project_id 必须是 ProjectStore 里的真实项目(与 REST adapter
  `_require_project` 404 语义同源),幽灵 id 首次调用即 fail loud,对象库零污染。

## Acceptance criteria

- [x] 猜错 id 被 `project_mismatch` 拒绝且 hint 给出正确 id;照 hint 重试成功
- [x] `prose_register_document`(原死循环那一步)绑定后正常返回 doc_id
- [x] 幽灵 project_id 写入被拒,对象库零污染
- [x] 护栏挂装配处,15 个工具 + 未来新增工具自动继承
- [x] pytest 全量绿(1169 passed / 34 skipped)

## 实现记录(2026-07-14,commit 0ad161e)

- `assets/mcp_actor.py`:`ActorRefASGI` → `AgentContextASGI`(现收 run 归属 +
  项目绑定两个 header);`assets/mcp.py` 工具装配处接绑定校验与存在性护栏。
- `mcp_tools.py` / `server/{app,agents,routers/messages}.py`:连接构造按 session
  注入 header / env。
- `bid-response-matrix/SKILL.md` 前置说明改为「不要猜,调一次工具让它把正确 id
  告诉你」。
- 新增 `tests/assets/test_mcp_project_guard.py`(175 行)覆盖两道护栏;
  真实 server 复现事故链路验证自愈闭环。
