# Hagent Base Prompt — Mp 子代理决策记录

源文件: docs/claude-code-prompt-full.md (609 行)
规约: docs/specs/2026-05-12-hagent-backend-design.md §6
生成时间: 2026-05-12

---

## 2026-05-14 迁移更新

- 将模型可见的文件工具名从 deepagents 内部名 `read_file` / `write_file` / `edit_file` 迁移为 Claude 兼容名 `Read` / `Write` / `Edit`。原因：当前 Hagent 面向模型暴露 Claude Code 风格工具名，base prompt 不应继续指导模型调用 deepagents 内部文件工具名。
- `Bash` 保持为模型可见 shell 工具名。
- 任务规划工作流改为 Claude 兼容 Task tools：`TaskCreate` / `TaskUpdate` / `TaskList` / `TaskGet`。历史上曾使用的 `write_todos` 规划指令已被替换并禁用；base prompt 不再要求模型用 `write_todos` 规划或追踪工作。
- 更新后 `prompts/hagent_base.zh.md` 计量：7037 tokens，206 行（cl100k_base）。

---

## 逐 section 处置

| 原 section / 段落 | 起止行 | 处置 | 理由 |
|---|---|---|---|
| 文件标题 + 版本元数据 | 1-6 | MODIFY | 标题改为 "Hagent — Base System Prompt"；版本号、Extracted 日期作为 Claude Code 专属元数据移除（不属于 base prompt 正文） |
| 开头身份段 | 8-9 | MODIFY | §6 表行: "开头身份段"。"Claude Code, Anthropic's official CLI for Claude" → "Hagent，一个基于 deepagents 的开源 Web Agent harness"；后半句 "interactive agent that helps users…" 完整保留并翻译 |
| 第一条 IMPORTANT（security） | 11 | KEEP | §6 表行: "两条 IMPORTANT（安全测试 + URL）" — 全文保留，整段翻译 |
| 第二条 IMPORTANT（URL） | 12 | KEEP | §6 表行: "两条 IMPORTANT（安全测试 + URL）" — 全文保留，整段翻译 |
| # System | 14-20 | KEEP（含 1 处 MODIFY + 1 处 DELETE） | §6 表行: "# System"。MODIFY：行 15 "rendered in a monospace font" → "渲染在 Web Chat UI 中，支持 Markdown（基于 CommonMark 规范）"。DELETE：行 19 hooks 整段（"Users may configure 'hooks'…"）。其余 4 条全保留 |
| # Doing tasks | 22-36 | KEEP（含 1 处 DELETE） | §6 表行: "# Doing tasks"。DELETE：行 34-36 末尾 `/help` 提示 + `github.com/anthropics/claude-code/issues` 链接整段。其余 11 条规则完整保留并翻译 |
| # Executing actions with care | 38-48 | KEEP | §6 表行: "# Executing actions with care" — 全文保留，举例（rm -rf / git / PR…）全部保留 |
| # Using your tools | 50-55 | MODIFY | §6 表行: "# Using your tools"。工具名映射更新：文件工具保持 Claude 兼容模型可见名 Read / Edit / Write；Bash 保持为 Bash。任务规划指令从历史 `write_todos` 改为 Task tools：3 步及以上复杂工作、显式 todo/task 列表请求、依赖/并行规划时使用 `TaskCreate` / `TaskUpdate` / `TaskList` / `TaskGet`；开始前标记 `in_progress`，完全完成后才标记 `completed`，未完成/失败/阻塞/部分完成不得标记完成。2026-05-14 Python Bash tool 接入后，shell-only 操作回到模型可见 `Bash`。 |
| # Tone and style | 55-70 | KEEP | §6 表行: "# Tone and style" — 全文保留（包括内嵌的 # Text output 子标题） |
| # auto memory（整段含 4 个 type / NOT to save / How to save / When to access / Before recommending / Memory and other forms） | 72-199 | KEEP（含路径 MODIFY） | §6 表行: "# auto memory"。MODIFY：行 74 路径 `~/.claude/projects/<project-slug>/memory/` → `{{working_directory}}/.hagent/memory/`，由 runtime 注入实际 workspace；行 74 中 "Write tool" → "Write 工具"。其余 4 类记忆定义、保存规则、索引规则、Before recommending 等全文保留。<examples> 块内英文 conversation 示例按规约原样保留（属于 prompt 内嵌示例，不翻译会破坏示例语义连贯性） |
| # Environment | 201-212 | MODIFY | §6 表行: "# Environment"。整段替换为 Hagent 运行时占位符（沙箱类型 / 工作目录 / 是否 git / 平台 / shell / 模型 provider / 模型 ID / 知识截止），由 runtime 注入 |
| # Context management | 214-215 | KEEP | §6 表行: "# Context management" — 全文保留 |
| # Session-specific guidance | 217-223 | DELETE | §6 表行: "# Session-specific guidance"。`! <command>` / Agent subagent_type / Explore / `/<skill-name>` / `/schedule` / `/ultrareview` 全部基于 Claude Code CLI 特有机制，Hagent 没有 |
| --- 分隔符 + # Tools 整段（含 Agent / Bash / Edit / Read / Write / ScheduleWakeup / ToolSearch / Skill / Deferred Tools 列表） | 225-609 | DELETE | §6 表行: "# Tools（完整工具 schema 列表）" — deepagents 自带工具注册表，运行时由 middleware 注入 |

### 表外推断（按决策树）

- **行 1-6 文件元数据**：§6 表未列。原文是 "# Claude Code — System Prompt / Version: 2.1.120 / Extracted: 2026-04-27"。按决策树：引用 "Claude Code" 实体 + 版本号属于 Claude Code 内部发布元数据 → MODIFY 为 Hagent 标题，移除版本/抽取日期（这些将由 Hagent 自身的发布流程管理，不属 base prompt 正文）。
- **行 142 `</types>` 闭合 / # auto memory 内嵌 <examples> 英文示例**：§6 表未明确处置 examples。按"KEEP + 翻译"默认 + 不允许添加原文没有的内容的规则，对话示例（user/assistant 短句）作为 prompt 内嵌技术示例保留英文原样（与"技术术语保留英文"原则一致；翻译示例会改变示例 demonstration 的语义边界）。

---

## 工具名映射统计

源文件 KEEP/MODIFY 段（行 1-225，即 DELETE 之后的剩余范围）中各工具名出现次数与替换情况：

| 原名 | 新名 | 源出现次数（KEEP/MODIFY 范围内） | 替换次数 | 备注 |
|---|---|---|---|---|
| Read | Read | 1（行 51） | 0 | 文件工具使用 Claude 兼容模型可见名 |
| Edit | Edit | 1（行 51） | 0 | 文件工具使用 Claude 兼容模型可见名 |
| Write | Write | 2（行 51 + 行 74 "Write tool"） | 0 | 文件工具使用 Claude 兼容模型可见名 |
| Bash | Bash | 1（行 51；行 220/223 在 DELETE 范围不计） | 0 | Python Bash tool 接入后保留为模型可见 `Bash` |
| write_todos | TaskCreate / TaskUpdate / TaskList / TaskGet | 1（历史行 52） | 1 | # Using your tools 的任务规划指令已改为 Task tools；`write_todos` 仅作为历史迁移说明保留在本决策文档中 |
| grep（deepagents 内置） | Grep | — | — | 2026-05-26：hagent 实现 CC 对齐 `Grep`（正则/ripgrep/output_mode），禁用 deepagents 小写 `grep`；base prompt 引导搜索内容用 `Grep` |
| glob（deepagents 内置） | Glob | — | — | 2026-05-26：hagent 实现 CC 对齐 `Glob`（mtime 倒序），禁用 deepagents 小写 `glob`；base prompt 引导找文件用 `Glob` |
| ls（deepagents 内置） | （无独立工具） | — | — | 2026-05-26：禁用 deepagents 小写 `ls`，目录列举回落 `Bash`（与 CC 一致） |

输出文件实际状态：Read / Edit / Write / Bash / Grep / Glob 为当前模型可见工具名；`TaskCreate`、`TaskUpdate`、`TaskList`、`TaskGet` 是当前任务规划工具名，必须保留在 base prompt 中。`write_todos` 不再作为规划指令出现在 base prompt 中；如出现 "使用 write_todos 规划并追踪工作" 应视为失败。`Bash` 为当前 shell 工具名，允许保留。

## 2026-05-26 增补：Grep / Glob 工具接入

`# Using your tools` 段新增「搜索内容用 `Grep`、按模式找文件用 `Glob`、不要用 Bash 跑 grep/rg/find」的引导（MODIFY，最小改动）；`# Skills` 段可见工具名清单补 `Grep`/`Glob`；`# 使用 subagent` 段「查找类任务」提示改为给出正则/glob 模式；`## Before recommending from memory` 的「grep 它」改为「用 `Grep` 搜它」。对应代码：`src/hagent/grep_tool/`（CC 对齐 Grep/Glob），`core.py` 的 `DISABLED_DEEPAGENTS_TOOLS` 追加 `grep`/`glob`/`ls`、`parent_tools` 注册 `Grep`/`Glob`。

---

## 自检报告

- [x] 无 `Claude Code` 残留（`grep -niE "claude code"` 结果: 0）
- [x] 无 `Anthropic` 残留（`grep -niE "anthropic"` 结果: 0）
- [x] 无 `Claude Opus` / `claude-opus-` 残留（`grep -niE "claude opus|claude-opus-"` 结果: 0）
- [x] `TaskCreate` / `TaskUpdate` / `TaskList` / `TaskGet` 作为当前 Task tools 指令保留；`write_todos` 规划指令已替换并禁用；`Bash` 工具名按 2026-05-14 Python Bash tool 设计保留
- [x] KEEP 段英文原文与中文译文逐段比对完成，无信息丢失（见下方 LLM-as-judge 抽样）
- [x] 列表结构（编号 / 项目符号）保留：原文 KEEP 段所有 ` - ` 项目符号 1:1 映射到输出
- [x] 强调标记（IMPORTANT / MUST / CRITICAL / Note）全部保留为英文大写形式
- [x] 代码块（```markdown frontmatter 示例）原样保留
- [x] inline code（路径 / flag / 工具名）反引号 `` ` `` 保留
- [x] `<types>` / `<type>` / `<examples>` 等 XML 标签结构保留

### tiktoken 计量（cl100k_base 编码）

| 文件 | tokens | 行数 |
|---|---|---|
| docs/claude-code-prompt-full.md | 11829 | 609 |
| prompts/hagent_base.zh.md | 7037 | 206 |

裁剪幅度：约 41.5% token 削减（主要来自 # Tools 整段 + # Session-specific guidance + hooks 段 + /help 段 DELETE）。

---

## LLM-as-judge 比对样本

随机抽 4 个 KEEP 段做英文原文 ↔ 中文译文语义对齐自查：

### 样本 1：第一条 IMPORTANT（行 11）

**英文原文**：
> IMPORTANT: Assist with authorized security testing, defensive security, CTF challenges, and educational contexts. Refuse requests for destructive techniques, DoS attacks, mass targeting, supply chain compromise, or detection evasion for malicious purposes. Dual-use security tools (C2 frameworks, credential testing, exploit development) require clear authorization context: pentesting engagements, CTF competitions, security research, or defensive use cases.

**中文译文**（hagent_base.zh.md L7）：
> IMPORTANT: 协助授权范围内的安全测试、防御性安全、CTF 挑战和教育场景。拒绝以下请求：破坏性技术、DoS 攻击、大规模目标定位、供应链入侵、用于恶意目的的检测规避。双重用途的安全工具（C2 框架、凭证测试、漏洞利用开发）需要明确的授权上下文：渗透测试任务、CTF 比赛、安全研究或防御性用例。

**判断**：语义完整。三层结构（assist / refuse / dual-use）全部保留；术语 CTF、DoS、C2 保留英文。

### 样本 2：# Doing tasks 第 5 条（原 prompt 行 28）

**英文原文**：
> Don't add features, refactor, or introduce abstractions beyond what the task requires. A bug fix doesn't need surrounding cleanup; a one-shot operation doesn't need a helper. Don't design for hypothetical future requirements. Three similar lines is better than a premature abstraction. No half-finished implementations either.

**中文译文**（hagent_base.zh.md L17）：
> 不要添加超出任务所需的功能、重构或引入抽象。bug 修复不需要附带清理；一次性的操作不需要 helper。不要为假设的未来需求做设计。三行相似的代码比过早抽象更好。也不要留下半成品的实现。

**判断**：语义完整。5 个独立语义点（不超 scope / 不附带 cleanup / 不设计未来 / 三行胜过抽象 / 不留半成品）全部对齐。

### 样本 3：# Tone and style 内嵌 Text output 段（原 prompt 行 60）

**英文原文**：
> Assume users can't see most tool calls or thinking — only your text output. Before your first tool call, state in one sentence what you're about to do. While working, give short updates at key moments: when you find something, when you change direction, or when you hit a blocker. Brief is good — silent is not. One sentence per update is almost always enough.

**中文译文**（hagent_base.zh.md L52）：
> 假设用户看不到大部分工具调用或 thinking——只看到你的文本输出。在你的第一次工具调用之前，用一句话说明你将要做什么。在工作时，在关键时刻给出简短的更新：当你找到某事时、当你改变方向时、或当你遇到阻碍时。简洁是好的——沉默不好。每次更新一句话几乎总是足够的。

**判断**：语义完整。"thinking" 作为术语保留；破折号（——）和三种关键时刻（find/change/blocker）枚举完整保留。

### 样本 4：# auto memory > Before recommending from memory 首段（原 prompt 行 186）

**英文原文**：
> A memory that names a specific function, file, or flag is a claim that it existed *when the memory was written*. It may have been renamed, removed, or never merged. Before recommending it:

**中文译文**（hagent_base.zh.md，对应段落）：
> 命名了特定函数、文件或 flag 的记忆是一个声明：它 *在记忆被写入时* 存在。它可能已被重命名、移除或从未 merge。在推荐它之前：

**判断**：语义完整。emphasis（斜体 `*…*`）保留；技术术语 flag / merge 保留英文；声明性语气保留。

---

## 结论

- 两份输出文件均符合 §6 规约的 Done 标准
- 所有 KEEP 段保持 1:1 句子边界 / 列表结构 / 强调标记 / 代码块对齐
- 所有 MODIFY 仅做最小改动，未压缩或合并段落
- 所有 DELETE 段在本表中显式列出，未漏判
- 工具名映射在 KEEP/MODIFY 范围内 100% 覆盖
- 无 Claude Code / Anthropic / Claude Opus 残留

---

## 2026-05-14 subagent 段落补充

在 `# Using your tools` 与 `# Tone and style` 之间新增 `# 使用 subagent` 段。讲解 `Agent` 工具（自管，CC schema：description + prompt + subagent_type?）、何时委派 / 不委派、可用内置 subagent（general-purpose / Explore / Plan）、撰写 subagent prompt 的要点。

| 段落 | 处置 | 理由 |
|---|---|---|
| `# 使用 subagent` | ADD | 当前 base prompt 缺乏委派指引，模型倾向把所有工作压在主线程，导致上下文膨胀；Hagent 自己实现了 `Agent` 工具（替代 deepagents `task` 工具），prompt 需明确告知 |

- 内置 subagent 名（`general-purpose` / `Explore` / `Plan`）与 `src/hagent/subagents/builtin.py` 一致。
- 段落正文为简体中文；无 `Claude Code` / `Anthropic` / `Claude Opus` / `write_todos` 残留。
- 工具名 `Agent`（驼峰）与 `src/hagent/subagents/agent_tool.py` 注册名一致。
- `tiktoken` 计量在下次主修订时重算（本次为增量补充）。

---

## 2026-05-15 skills 段落补充

在 `# 使用 subagent` 后新增 `# Skills` 段。原因：Hagent 现在暴露 Claude Code 风格 `Skill` 工具，并且技能目录由 Hagent 自管；不能直接使用 DeepAgents `SkillsMiddleware` 默认提示，因为它会指导模型调用 Hagent 已隐藏的 deepagents 内部文件工具名。

- 模型应在匹配 skill 或用户引用 slash skill 时先调用 `Skill`。
- prompt 明确列出当前 Hagent 可见工具名，避免模型退回 deepagents 内部工具名。
- 该段不替代动态 skills catalog；动态 catalog 由 `HagentSkillsMiddleware` 注入。

---

## 2026-05-19 — sandbox 模式段落

**KEEP**：sandbox 模式段落（`/workspace` 是 LLM 看到的根、host 路径不可达、网络开放、secrets 空、容器是隔离边界）。

**MODIFY**：sandbox 启用时 working_directory 总是 `/workspace`（render_base_prompt 的 working_directory 参数自动反映 sandbox.workspace_dir）。

**DELETE**：无。

依据：spec `docs/specs/2026-05-19-hagent-sandbox-design.md` §3.3、§5.2、§5.5；实现 plan T14。

---

## 2026-05-20 — sandbox 段落改为条件渲染（仿 CC `getSimpleSandboxSection`）

**MODIFY**：把 sandbox 模式段从 `prompts/hagent_base.zh.md` 静态末尾段**移到** `src/hagent/config.py::render_base_prompt` 内的 `_sandbox_section()` 条件附加块。

- 仅当 `sandbox_type in {"HagentDockerSandbox", "HagentDaytonaSandbox"}` 时才把这段附加到 prompt 末尾；host 模式 LLM 看不到 sandbox 字样，省 token、不误导。
- 渲染内容动态：把当前 `sandbox_type` 与 `working_directory` 注入文本。
- 结构对齐 Claude Code `src/tools/BashTool/prompt.ts::getSimpleSandboxSection()`：`## Command sandbox` 标题 + 一行总述 + `Filesystem`/`Network`/`Secrets` JSON-like 描述 + bullet 条款。
- 选 CC 的 Mode B（`allowUnsandboxedCommands=false`，policy-locked，无 per-command bypass）作为基线——hagent 的容器边界天然就是这种约束。

**对齐 CC 的部分**：标题、总述、`Filesystem`/`Network` JSON 风格、"All commands MUST run inside the sandbox" 主条款。

**因冲突而剔除/改写**：

- 移除 CC 的 `dangerouslyDisableSandbox` 决策 SOP：Hagent 的 BashSchema 保留了 `dangerouslyDisableSandbox` 字段用于 schema 兼容，但 `bash_tool/permissions.py` 注释明示"compatibility field; does not bypass"。prompt 改为告诉 LLM 该参数**不生效**。
- 移除 CC 的 `$TMPDIR` 提示：Hagent docker container 内 `/tmp` 是普通可写 tmpfs，无 `$TMPDIR` 约定。
- 移除 CC Mode A bypass SOP 分支（"Evidence of sandbox-caused failures..."）：Hagent 没有 host-side 单条命令 bypass 路径，整个 BashRuntime 通过 `SandboxShellProvider` → `docker exec` 路由。
- `Filesystem.write.allowOnly` 用 sandbox-internal 路径（`/workspace`），而非 CC 的 host 路径（host 上不存在 `/workspace`）；新增 `hostPaths:"not reachable"` 字段提示 LLM 容器边界。
- 新增 `Secrets: not injected` 项：CC sandbox 可注入 secrets（macOS keychain 等），Hagent 设计是 secrets 绝不入沙箱（spec D6）。

**DELETE**：`prompts/hagent_base.zh.md` 末尾的 `## Sandbox 模式（启用时）` 静态段。

依据：用户对 CC 行为的对照反馈（2026-05-20）；参考 `docs/cc-recovered-main/src/tools/BashTool/prompt.ts:172-273`。

---

## 2026-07-12 — Tender 重设计（面向 Prose 标书平台）

背景：base prompt 原为 CC system prompt 的移植翻译，身份自述是基础设施（deepagents harness）、任务主线全是软件工程规范，与 Prose 的实际用户（标书从业者）错位。本次按「学 CC 设计哲学、不搬其内容」的原则整体重写：身份改为「你是 Prose，标书智能体」，任务主线改为标书全流程工作，回复风格定为温暖、专业、可靠，全文以中文母语标准重写消除翻译腔。

用户拍板的两个决策：身份命名用 Prose（身份即产品）；软件工程任务规范完全移除，一条不留。

### 逐 section 处置

| 原 section | 处置 | 理由 |
|---|---|---|
| 开头身份段 | MODIFY | "Hagent，基于 deepagents 的开源 Web Agent harness" → "你是 Prose，一个 AI 原生标书平台的智能体"；新增用户画像（标书从业者、时间紧、废标代价高）与交互形态（对话执行流 + artifact 画布、拖入文件） |
| 第一条 IMPORTANT（安全） | KEEP | 全文保留，不动 |
| 第二条 IMPORTANT（URL） | MODIFY | 去掉"帮助用户进行编程"限定，改为通用表述（只用用户提供的、工作区文件中的、确有把握真实的链接） |
| # System | KEEP（重写措辞） | 5 条规则功能全保留（输出展示 / 权限模式 / system-reminder / prompt injection / 自动压缩），措辞去翻译腔 |
| # Doing tasks | MODIFY（重构为「# 做事」） | 主线重写为标书全流程：解析招标文件（商务/技术要求、评分办法、资质门槛、废标项）、编制与改写投标文件、合规自查、周边通用工作。软件工程规范（代码注释、OWASP、重构克制、向后兼容 hack、UI dev server 验证）全部 DELETE。保留并泛化的通用原则：宽泛指令放场景里理解、探索性问题 2-3 句建议+取舍、不越 scope 不留半成品、优先 Edit 不用 Write 另起文件。ADD：事实优先原则（金额/日期/资质以文件为据，无据留占位符，宁可留空不可编造） |
| # Executing actions with care | KEEP（重构为「# 谨慎行动」，例子换域） | 可逆性分级、批准不跨场景、不用破坏性动作图省事、意外状态先调查的精神全保留；示例从 git/rm -rf/PR 换成标书场景（覆盖章节草稿、批量替换、对外发布/上传第三方） |
| # Using your tools | KEEP（压缩措辞） | 专用工具优先于 Bash、Grep/Glob 引导、Task tools 规划规则（in_progress/completed 纪律）、并行调用原则全保留 |
| # 使用 subagent | KEEP（压缩措辞） | Agent 参数、何时委派/不委派、内置 general-purpose/Explore/Plan（与 src/hagent/subagents/builtin.py 一致）、prompt 撰写要点全保留 |
| # Skills | KEEP（压缩措辞） | Skill 工具触发规则、`/<skill-name>` slash 引用、可见工具名清单全保留 |
| # Tone and style | MODIFY（重构为「# 语气与风格」） | 从 CLI 工程师风改为「温暖、专业、可靠」三词拆解：温暖=同事感/不奉承/禁空洞夸赞；专业=结论先行/形态匹配分量/引用给出处；可靠=如实报告/不夸大。保留：emoji 限制、首次工具调用前一句话说明、关键节点简短更新、冷启动可读、回合总结一两句 |
| # auto memory | KEEP（整体压缩 + 示例换域） | 路径 `{{working_directory}}/.hagent/memory/`、四类记忆、<types>/<examples> XML 结构、两步保存流程（frontmatter + MEMORY.md 索引）、NOT to save、When to access、Before recommending 验证、memory vs Plan/Task 边界全保留。<examples> 从英文编码场景对话重写为中文标书场景对话（商务经理 / 评分办法表格 / 开标日期 / 网盘资质目录）——本次为原生撰写而非翻译，不存在 2026-05-12 记录中"翻译破坏示例语义"的问题 |
| # Environment | KEEP | 8 个占位符逐字保留（{{sandbox_type}} {{working_directory}} {{is_git_repo}} {{platform}} {{shell}} {{model_provider}} {{model_id}} {{knowledge_cutoff}}），与 config.py::render_base_prompt 的替换表一致 |
| # Context management | KEEP | 全文保留 |
| sandbox 段 | （无变化） | 维持 2026-05-20 决策：不写静态段，由 config.py::_sandbox_section 渲染时条件注入 |

### 自检

- [x] 无 Claude Code / Anthropic / Claude Opus / claude-opus- 残留
- [x] TaskCreate / TaskUpdate / TaskList / TaskGet 保留；无 write_todos
- [x] Read / Write / Edit / Bash / Grep / Glob / Agent / Skill 模型可见工具名全部在正文出现
- [x] 8 个 `{{占位符}}` 逐字保留
- [x] 测试断言同步：tests/test_config.py、tests/test_core.py 的 "你是 Hagent" → "你是 Prose"
- [x] ./scripts/check_base_prompt.sh 通过（见下方验证）

### tiktoken 计量（cl100k_base 编码）

| 文件 | tokens | 行数 |
|---|---|---|
| prompts/hagent_base.zh.md（2026-05-14 移植版） | 7037 | 206 |
| prompts/hagent_base.zh.md（2026-07-12 重设计版） | 5827 | 208 |

削减约 17%。略高于计划的 4000–5500 参考区间：按计划"以表达完整为准，不为凑短删功能段"的原则，memory / subagent / skills 等 harness 协议段功能全保留是主要占比。

---

## 2026-07-12 增补 — 移除 # auto memory 段

**DELETE**：`# auto memory` 整段（含 Types of memory / What NOT to save / How to save / When to access / Before recommending / Memory and other forms of persistence 全部小节）。

理由：现阶段不做记忆功能，prompt 保留该段会引导模型向 `{{working_directory}}/.hagent/memory/` 写入无人消费的文件。待记忆功能立项后按 2026-07-12 重设计版的该段（见 git 历史）恢复并复核。

配套：`tests/test_core.py::test_create_hagent_injects_backend_workspace_into_prompt` 移除两条 `.hagent/memory/` 路径断言（workspace 注入断言保留）。`{{working_directory}}` 占位符在正文仅剩 Environment 段一处，渲染逻辑不受影响。

### tiktoken 计量（cl100k_base 编码）

| 文件 | tokens | 行数 |
|---|---|---|
| prompts/hagent_base.zh.md（2026-07-12 重设计版，含 memory） | 5827 | 208 |
| prompts/hagent_base.zh.md（本次移除 memory 后） | 3445 | 108 |

---

## 2026-07-12 增补 — 回复中屏蔽文件路径

**ADD**：`# 语气与风格` 新增一条：回复里不出现文件路径，用文档名称指代文件；出处用文件名加条款/章节号；仅用户明确问到存放位置时才说明路径。

理由：实测发现模型完成 Write/Edit 后习惯性汇报 sandbox 路径（"已写入 /workspace/xxx.md"）。对平台用户而言路径是沙箱内部细节，文档呈现在画布上，路径只是噪声。原 prompt 无反向指令，需显式覆盖模型默认行为。规则限定"面向用户的回复文本"，工具调用与 subagent 简报仍使用真实路径，不受影响。

### tiktoken 计量（cl100k_base 编码）

| 文件 | tokens | 行数 |
|---|---|---|
| prompts/hagent_base.zh.md（移除 memory 版） | 3445 | 108 |
| prompts/hagent_base.zh.md（本次增补后） | 3583 | 109 |

---

## 2026-08-30 增补：语气与风格治理（agent-voice）

**MODIFY**：§「# Tone and style」（输出文件「# 语气与风格」章节的 bullet 列表；三段温暖/专业/可靠散文不动）。四处变更：

1. **ADD 语言硬规则**：面向用户的一切文本一律简体中文，含工具调用之间的过程更新；代码、命令、文件名与专有技术名词保留原文。理由：真实会话中子代理过程旁白最高 90% 为英文，仅靠中文写就的 prompt 不足以约束过程文本的语言。
2. **MODIFY 路径屏蔽推广为内部细节总原则**：「回复里不出现文件路径」扩展为「不出现工作环境的内部细节」——文件路径、工具名、JSON/字段名、状态枚举、条目编号、校验分数与阈值均属实现层，对用户只说业务语言，并附三组对照示例。理由：真实会话中主 agent 回复 36~42% 含状态枚举/条目编号/校验分数等内部词汇，单禁路径盖不住同类泄漏。
3. **MODIFY 过程更新节奏**：从「关键节点」收紧为「阶段边界」，明确连续的同类操作（逐批提交、逐个文件读取）不逐步播报，补「刷屏更不好」。理由：单轮任务产生 10~20 条逐步旁白，刷屏淹没关键信息。
4. **ADD 复杂任务最终汇报口径**：按「你拿到了什么 → 哪里需要你出手」组织，先说产出与它在哪，再列需用户确认或补充的事项（按影响排序，每条一句话）；数字和状态为用户判断服务，不罗列内部计量。

依据：仓根 `.scratch/agent-voice/PRD.md`。

### tiktoken 计量（cl100k_base 编码）

| 文件 | tokens | 行数 |
|---|---|---|
| prompts/hagent_base.zh.md（回复中屏蔽文件路径增补版） | 3583 | 109 |
| prompts/hagent_base.zh.md（2026-08-30 本次增补后） | 3875 | 110 |
