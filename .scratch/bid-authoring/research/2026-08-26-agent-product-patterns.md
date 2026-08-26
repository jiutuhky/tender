# 下半场调研与规划补充 —— 前沿 agent 产品范式 × 标书垂类 × 技术选型

> 日期 2026-08-26 · 方法 search-first（三路 Opus 5 调研代理并行 + 代码库摸底）· 基线 `PRD.md`（五道闸门）
> 产出：本文 + 分页原型画布「Prose 标书编制全流程」（源文件 `../design/`，构建 `node build.mjs`）。
> 本文只记录**对 PRD 的增量**：调研结论、被确认或被修正的设计决策、原型里落地的交互。PRD 已定的东西不重复。

---

## 0. 一句话结论

前沿 agent 产品（Cowork / Claude Code / Trae SOLO / Manus / Grok Bot / Deep Research / Antigravity / Jules / Notion Agent / Word Agent Mode）的共识**不是「让 AI 更自动」，而是把智能体的中间状态物化成人可批注、可排序、可回滚的对象**——Progress 面板、`todo.md`、Artifact、Wide Research 矩阵、可编辑计划、行内引用。

在 Prose 里这个对象**已经存在**：应答矩阵与骨架。下半场的全部交互都长在它上面，不长在聊天流上。这与 PRD「大纲是记分卡的投影」「结构入库、正文入文件」两条主张完全一致，调研没有推翻任何一条架构分界线，只在交互节奏上补了六条具体机制（§2）。

---

## 1. 调研 A · 前沿 agent 产品的交互机制（可直接迁移的部分）

### 1.1 逐产品要点（来源见链接）

| 产品 | 值得抄的机制 | 来源 |
|---|---|---|
| **Claude Cowork** | 右侧三栏 Progress / Project / Context；产出物进 Artifacts 面板；选中草稿文字「Edit with Claude」只改选中处；权限三档 Manual / Auto / Skip，删除永远弹窗；**Dispatch**：子任务各自带状态 Running / Awaiting input / Awaiting answer / Completed / Error，**权限请求 10 分钟不回应自动拒绝并继续跑**；交付物带 citations 回到源文件 | [Get started](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork) · [Use Cowork safely](https://support.claude.com/en/articles/13364135-use-claude-cowork-safely) · [Dispatch](https://claude.com/docs/cowork/guide/dispatch) · [产品指南](https://claude.com/blog/the-claude-cowork-product-guide) |
| **Claude Code** | plan mode 三选一「Yes, and use auto mode / Yes, manually approve edits / No, keep planning」，`Ctrl+G` 把计划扔进编辑器手改；Task panel 列并发子代理，只把结论回主对话；checkpoint / rewind 分别恢复代码或对话；`/goal` 可验证完成条件 + 独立小模型判定 | [permission-modes](https://code.claude.com/docs/en/permission-modes) · [sub-agents](https://code.claude.com/docs/en/sub-agents) · [checkpointing](https://code.claude.com/docs/en/checkpointing) · [goal](https://code.claude.com/docs/en/goal) |
| **Anthropic 工程博客** | Orchestrator-Workers / Evaluator-Optimizer；长任务 harness：进度文件 + 特性清单（只准改 `passes` 字段）+ 强制端到端验证；**Sprint Contract**：生成方与评审方动工前谈定可测的成功标准；模型会自夸，评审要外部化 | [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) · [Effective harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) · [Harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps) · [Human-agent teams](https://claude.com/blog/building-effective-human-agent-teams) |
| **Trae SOLO** | Flow 模式：面板跟随阶段自动切换，执行期只读，双击即退出接管；PRD 是唯一事实来源 + 显式确认门；进度日志用业务语言（「正在构建 Features 页面」）；Select & Edit 在预览里选元素用自然语言改 | [tool-panels](https://docs.trae.ai/ide/tool-panels) · [解读](https://www.iweaver.ai/guide/from-single-prompt-to-full-deployment-trae-2-0-solo-is-all-you-need/) |
| **Manus** | `todo.md` 是可见的活检查清单；右侧「Manus 的电脑」可随时接管；**Wide Research 并行子代理的产物先落成可排序矩阵**；幻灯片逐页生成 + 单页魔法棒修复；Replay 回放链接 | [Wide Research](https://manus.im/docs/features/wide-research) · [接管](https://help.manus.im/en/articles/11711218-how-can-i-take-over-manus-browser-or-vs-code) · [1.5](https://manus.im/blog/manus-1.5-release) |
| **Grok Bot** | 常驻同事：「需要批准时才回来，不是每步问方向」；看一遍学会成 Routine；产出落在人类会放的地方 | [Unite.AI](https://www.unite.ai/xai-launches-grok-bot-always-on-ai-teammates-with-their-own-cloud-computers/) · [指南](https://composio.dev/content/guide-to-frok-bot) |
| **OpenAI / Google** | Deep Research：先澄清 → 可编辑计划 → 行内可点引用；Gemini：**「说 go ahead 不算批准」，必须显式翻 flag**；Antigravity：Manager 面列所有 agent + pending approvals，**在 Artifact 上留行内评论、agent 不停机吸收**；Jules：Approve plan，**不响应则超时自动批准**；Canvas：批注 hover → Apply，选中段只改该段 | [Deep Research FAQ](https://help.openai.com/en/articles/10500283-deep-research-faq) · [Gemini DR](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agents/use-deep-research) · [Antigravity](https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/) · [Jules](https://jules.google/docs/code/) · [Canvas](https://help.openai.com/en/articles/9930697) |
| **Notion / M365 Copilot** | Notion Agent 三标签 Chat / Activity / Settings，每处改动可经版本历史撤销；Word Agent Mode 直接操作文件结构与模板，四阶段 Planning → Researching → Drafting → Reviewing；Researcher 来源范围可开关 | [Notion](https://www.notion.com/help/custom-agents) · [Word Agent Mode](https://office-watch.com/2026/copilot-agent-mode-word-excel-powerpoint/) · [Researcher](https://www.microsoft.com/en-us/microsoft-365/blog/2025/03/25/introducing-researcher-and-analyst-in-microsoft-365-copilot/) |

### 1.2 对比表

| 产品 | 计划审批 | 进度可视化 | 并行子任务 | 中断 / 回滚 | 产出物编辑 | 溯源 |
|---|---|---|---|---|---|---|
| Cowork | 先审方案再开工；Dispatch 权限转发 + 10 分钟超时拒绝 | Progress 逐步打勾 | 子任务各带状态 | 中途改道；另一设备接管 | Edit in place | citations 回源文件 |
| Claude Code | plan mode 三选一 + Ctrl+G 手改 | Task panel | 默认并发 20，只回结论 | checkpoint / rewind | Design 画布 / Artifact | — |
| Trae SOLO | PRD 显式确认 | 业务语言日志 + Flow 面板跟随 | 弱 | 双击退出 Flow | 选元素自然语言改 | 回溯 PRD |
| Manus | todo.md 可改 | 「Manus 的电脑」 | Wide Research → 矩阵 | 接管 / Replay | 逐页 + 局部重生 | 报告附来源 |
| Gemini DR / Antigravity / Jules | Edit plan / Approve plan（超时自动批） | Manager 面 | 多 agent 并列 + pending approvals | reject 计划；diff 审阅 | Artifact 行内评论 | 分节引用 |
| Notion / Word Copilot / Canvas | 四阶段计划 | Activity / 侧栏进度条 | 弱 | 版本历史全量撤销 | 批注 Apply；全局滑杆 + 局部指令 | 来源清单可点回 |

### 1.3 十二条可迁移原则（与 PRD 的对应）

1. **计划是可编辑对象，不是一段话**——G3 开跑前一次批准整条轨迹（PRD §5.4 已有），补：三选一 + 可在骨架上直接改。
2. **审批稀疏而高价值**——五道闸门即五个检查点，闸门之间只播报（PRD 已有）。
3. **无人应答要有预设策略**——Cowork 10 分钟拒绝、Jules 超时批准。Prose 取折中：计划审批 10 分钟未回应按「逐节验收」档开跑；不可逆动作（导出覆盖、全量重抽）永远等人。**新增。**
4. **进度用业务语言**——活动条「正在撰写 3.2 系统架构设计」，不报工具调用（现有 activityLine 机制已如此）。
5. **并行子任务先落成矩阵再落成文章**——章节验收矩阵视图（列表形态的骨架，可按状态 / 分值 / 待办排序）。**新增**，原型工具栏「验收矩阵」按钮。
6. **验收粒度 = 生成粒度 = 节**——每节一个 Run（PRD §6.6 已有）。
7. **面板跟随阶段切换，且留逃生门**——中心舞台随闸门换主角（矩阵 → 骨架 → 终检），画布随时可平移（现有编排语汇已支持）。
8. **反馈用行内批注，agent 不停机吸收**——写作台选中段落三选一：让智能体改这段 / 补锚记 / **留批注不打断**。**新增。**
9. **每条事实可点回原文，来源范围可开关**——锚记 chip 可点回证据；写作简报「证据范围：项目上传 · 机构证据库 · 公网关」。**新增（公网开关）。**
10. **一切可撤销、可回放**——章节版本 v1…vN + Run 执行流页签 + 工作区 git checkpoint（PRD 已有基础，原型把它露出为写作台头部的「执行流 / 版本」页签）。
11. **合规评审外部化**——G4 全部确定性检查（PRD 已有）；**不**引入「评委打分」LLM 评审（Sprint Contract 的精神由写作简报里的「评委据此打分」承担：写作前就把评分规则给到写作者）。
12. **Project 级记忆 + 常驻口径**——全局口径卡随简报下发（PRD 已有）；机构级证据库是复利起点（PRD M3）。

「等你回答」升格为章节一等状态（Cowork Awaiting answer）：只挂起本节、不占并发、不阻塞其他节；回答落在输入坞即可。**新增**，原型 G3 主视图与看板均已体现。

---

## 2. 对 PRD 的六处增量决策

| # | 决策 | 落点 | 来源 |
|---|---|---|---|
| D1 | G3 计划审批为三选一（批准并自动撰写 / 批准但每节先看 / 先改计划），10 分钟未回应按第二档开跑 | 消息窗计划卡（原型 Approval） | Claude Code plan mode · Jules · Cowork Dispatch |
| D2 | 「等你回答」为章节一等状态，只挂起本节 | 章节卡行、子代理看板、工具栏状态带 | Cowork Dispatch |
| D3 | 章节验收矩阵：骨架的列表形态，可排序、逐行验收 | 工具栏「验收矩阵」 | Manus Wide Research |
| D4 | 写作台就地协商三选一，「留批注不打断」进入本节 Run | 写作台弹层 | Antigravity · Cowork |
| D5 | 证据范围开关（项目上传 / 机构证据库 / 公网，默认关公网） | 写作简报「可用证据」页签 | M365 Researcher |
| D6 | 终检 warning 可豁免但留痕并写入终检报告；error 必须清零 | 终检抽屉「豁免并留痕」 | Anthropic human-agent teams（放权按表现递进） |

---

## 3. 调研 B · 标书垂类现状与技术选型

> **可达性声明（必读）**：本节由重派的第三路代理完成时，会话的 WebSearch 配额已耗尽，且 Baidu / Bing / DuckDuckGo 等搜索引擎与 g2.com / loopio.com / github.com / docxtpl 文档 / spellbook 等站点被网络策略拦截。因此 **3.1 国内产品与 3.3 用户抱怨两块零取证**（内容来自模型先验，标 ⚠️，不得写入对外材料，需人工复核）；3.2 欧美产品、3.4 长文生成方法、3.5 排版管线（pandoc / python-docx 部分）、3.6 引用锚记（ALCE）有一手来源。

### 3.1 国内编标派 ⚠️ 未核证（待人工实测）

待验证假设：主流是「上传招标文件 → 抽评分办法 / 资格条件 → 套模板生成大纲 → 分章填充 → 导出 Word」的四到五步向导，非 agent 自主编排；大纲多来自行业模板库 + 评分表映射，而非从招标文件真实结构反推；企业资料库停留在附件 / 证照上传级，无证据分级与复用溯源；导出依赖固定 docx 模板，目录域、分节页码、盖章位常需人工返工；低客单价订阅或按份计费，客户为中小投标企业与代写机构。

> 补做清单：钛投标、易中标、智标、标书AI 官网与试用；知乎 / 小红书实测帖；企查查确认主体与融资。

### 3.2 欧美 RFP 派（有来源）

| 产品 | 大纲来源 | 章节生成 | 资料库 | 排版导出 | 合规检查 | 溯源 | 来源 |
|---|---|---|---|---|---|---|---|
| AutogenAI | 平台内构建自定义 proposal 大纲并跟踪进度 | Write 模块 + agentic Research（自有库 + 互联网） | 组织知识库 | 未披露 | Gamma Review 合并多轮评审 | 未披露 | [autogenai.com](https://autogenai.com/) · [platform](https://autogenai.com/platform/) |
| Responsive（原 RFPIO） | 未披露 | AI Assistant 答题式 | 中心化内容库 8.7M Q&A | **Word / Excel** | **compliance matrix 跟踪** | 未披露 | [responsive.io](https://www.responsive.io/) · [pricing](https://www.responsive.io/pricing)（Emerging 版起价 $10,000） |
| Arphie | 未披露 | AI agent 起草 | **直连 Drive / SharePoint / Confluence / Notion** | 未披露 | 未披露 | **每条答案带来源 + 置信分数** | [arphie.ai](https://arphie.ai/) |
| DeepRFP | **RFP shredding → 需求 / 风险 / 截止期** | AI generator + 润色 | 上传历史标书与企业资料 | 未披露 | **自动 compliance matrix** + compliance / clarity / impact 三维评审 | 未披露 | [deeprfp.com](https://deeprfp.com/)（$89 / 月 / 人） |
| Loopio | 域名被拦，未取证 | | | | | | |

结论：**compliance matrix 自动化（Responsive / DeepRFP）与来源可解释（Arphie）是两条已被验证的差异化轴，但没有一家同时做好**；「矩阵 → 大纲 → 并行撰写 → 合规 → 规范 docx」的完整链路在公开信息里未见对标者——既是空位，也意味着无现成范式可抄。这与 PRD §3「竞争坐标」的判断一致。

### 3.3 用户抱怨 ⚠️ 未核证（作访谈提纲用）

待验证假设：内容库陈旧与去重；生成内容「正确但没有针对性」；导出后排版返工；引用不可核；合规检查漏项。「生成了也不敢直接用」的环节推测为一切**可被判废标或构成法律承诺的字段**：技术偏离表的数字、业绩案例、资质与人员配置、价格条款——与 PRD 把「断言有据」设为硬门禁的判断吻合，但仍需真实投标人访谈验证。

### 3.4 大纲驱动的长文生成方法（有来源）

- **STORM**（[arXiv:2402.14207](https://arxiv.org/abs/2402.14207)）：预写作三步——多视角发现 → 模拟多视角写作者向专家提问并以可信网源接地 → 整理成大纲；相对 RAG 基线组织性 +25pp、覆盖度 +10pp。专家指出的两个失效模式对标书致命：**源偏见传递**与**把不相关事实强行关联**（正是「生成了不敢用」的技术根因）。
- **Co-STORM**（[arXiv:2408.15232](https://arxiv.org/abs/2408.15232)）：多 agent 互相讨论、用户旁观介入、动态 mind map 组织信息。
- **LongWriter / AgentWrite**（[arXiv:2408.07055](https://arxiv.org/abs/2408.07055)）：有效输出长度受 SFT 样本长度约束而非上下文窗口；plan-then-write 把长文拆成子任务，把上文摘要 + 全局 plan 注入每个子任务。

**对 Prose 的映射**：应答矩阵天然就是 STORM 的「大纲」产物，且比对话式生成可靠——**大纲来自招标文件的硬约束，不需要模型创造**，这是相对通用 deep research 架构的最大优势。并行章节一致性在 AgentWrite 的做法之上再加两层确定性约束：(a) 每节写作前注入**冻结的全局事实卡**（公司名 / 资质编号 / 工期 / 报价口径），事实不由分身自行检索——即 PRD 的口径卡，本文把它升格为「事实卡」，字段化；(b) 成文后跑**跨章一致性 diff**，比对同一事实卡字段在各章的实例化结果——即 PRD §4 G3 的交叉一致性检查，实现路径明确为「按锚记 / 字段比对」而非印象分。

### 3.5 md → docx 确定性排版管线：采用 / 扩展 / 自研

- **采用**：pandoc + `--reference-doc`。沿用参考文档的样式表与文档属性（页边距、纸张、页眉页脚、表格与编号方案），正文内容被忽略；`--toc` 对 docx **插入真正的 TOC 域**由 Word 构建——对目录域需求是利好。限制：只有 pandoc 显式使用的那批样式能可靠传递。（[pandoc MANUAL](https://pandoc.org/MANUAL.html)）
- **扩展**（工作量真正所在）：pandoc 覆盖不到的恰是中文标书的强需求——分节独立页码（封面不编号 / 目录罗马 / 正文阿拉伯）、页眉页脚域、跨页表头重复（`tblHeader`）、复杂合并单元格、盖章位占位。这些在 OOXML 的 `sectPr` / 域代码 / `trPr` 层。做法：pandoc 产出 docx 后用 **python-docx 做 XML 级后处理**（高层 API 只到 `sections` 的 11 个属性，官方文档不涉及页码域；但它允许直接操作底层 XML）。（[python-docx sections](https://python-docx.readthedocs.io/en/latest/user/sections.html)）
- **自研**：只自研「**排版规范描述 → OOXML 补丁**」这一薄层，把封面、分节页码、盖章位做成声明式配置；不自研 docx 写出器。docxtpl（Jinja2 进模板，适合封面与固定表单）、docx-js、LibreOffice / OnlyOffice headless 本次域名被拦未取证 ⚠️。
- **已知坑**：① `--toc` 产的是域，首次打开不更新则目录为空——reference-doc 预置「打开时更新域」或交付说明；② 中文字体必须在 reference-doc 样式里同时设 `w:eastAsia`，否则回退默认字体；③ 合并单元格 + 跨页表头重复叠加时 Word 与 WPS 渲染不一致，**验收基准用 WPS**（国内投标现场多为 WPS）；④ 严禁引入 LibreOffice 二次转换，会丢域。

> 这条选型与 PRD §6.5 一致；新增的是「python-docx 走 XML 补丁层」「WPS 为验收基准」两条实施约束，以及 spike 的验收清单（分节页码 / 页眉页脚域 / 跨页表头 / 合并单元格 / 盖章位 / 中文字体）。

### 3.6 事实断言 → 行内锚记 → 确定性解析（有来源）

- **ALCE**（[arXiv:2305.14627](https://arxiv.org/abs/2305.14627)）：首个评测「带引用的 LLM 生成」的基准，指标把 **citation recall**（断言有多少被引用覆盖）与 **citation precision**（引用是否真的支撑该句）分开；ELI5 上最好的模型也有 50% 情况缺完整引用支撑。含义：**锚记不能靠模型自觉**，「每条断言是否带锚」与「锚是否真的支撑断言」要分开度量、分开修——原型写作台「锚记检查」页签只做了前者，后者（锚记与证据摘要的语义支撑度）留作 M3 的评估项。
- Arphie 的「来源 + 置信分数」是唯一取证到的商业化先例，说明可解释在提案场景是可售卖卖点。
- Perplexity / Deep Research 引用编号、Harvey / Spellbook cite check ⚠️ 未取证。通用做法（模型只输出稳定 ID 锚记如 `[^E:C-2024-0318]`，渲染层确定性查表解析成链接，解析失败即报错而非静默丢弃）是 PRD §6.3 的路线，本次调研未发现反例。

### 3.7 关键判断

1. **矩阵即大纲是护城河**：欧美只有 DeepRFP 把 shredding → compliance matrix 做通，且面向 freelancer，没有并行撰写与规范 docx。
2. **可信度是命门**：STORM 的 over-association 与 ALCE 的 50% 缺引用共同指向「事实卡冻结 + 强制锚记 + 跨章 diff」三件套必须是一等公民。
3. **docx 层要买不要造**：pandoc 打底 + python-docx XML 补丁，自研压到「规范 → OOXML 补丁」薄层，WPS 做验收基准。
4. **必须补的调研**：国内四家产品实测（本次零取证）与真实投标人「不敢用」访谈——3.3 目前全是假设。

---

## 4. 原型：六页画布怎么读

画布 https://claude.ai/code/artifact/616e143f-3788-44c3-a87d-2757c43b859c（源 `../design/`）

| 页 | 画板 | 展示什么 |
|---|---|---|
| 总览 | Flow · Architecture | 五道闸门（智能体做什么 / 人确权什么 / 硬门禁 / 舞台形态）+ 检查点节奏四条规则；四域三链接、`prose_*` 工具面扩展、`prose_get_section_brief` 契约、Run fan-out、导出管线 |
| G1 定策 | Main · Adjudicate | 骨架成为中心舞台（三册纵列 + 章节卡四行语法 + 健康度徽），工具栏即状态带，「确认骨架」闭合前置灰；裁决队列抽屉（未挂接 / 低置信 / 已裁决） |
| G2 备料 | Evidence | 缺料清单抽屉：按影响分三档（实质性 / 得分 / 可信度），每条三种认领 |
| G3 成文 | Writing · Approval · Desk | 12 节并行：多卡进行中、看板每路一行（身份色相）、消息窗只报总控、「等你回答」；计划审批三选一；写作台（正文纸面 + 四页签简报 + 就地协商弹层，页签可点） |
| G4 合规 | Compliance | 终检清单四组确定性检查，可真按「已修复，复检」销项，error 清零解锁导出 |
| G5 成册 | Export | 装订导出：分册 / 排版规则 18 项 / 模板 / 正副本 / 输出 / 签发；边界说明 |

设计基线：界面沿用 `feat/trace-preview-layer` 现有工作台（顶栏 / 画布工具栏 / 停靠列四矩阵卡 / Bot 消息窗 / 子代理看板 / 输入坞与活动条），按 `globals.css` 实测值复刻；新增的只有章节卡、健康度徽、三个抽屉、写作台与导出面板。数据全部来自 `sample-tender.md`。

---

## 5. 下一步（不改 PRD 的里程碑顺序）

1. **M1 骨架贯通**照 PRD 动工；本文 D1–D6 中与 M1 相关的只有状态带与「确认骨架」置灰逻辑。
2. **排版保真度 spike** 与 M1 并行（PRD §10.1）；§3 的选型结论落地后决定正文中间表示。
3. `prose_get_section_brief` 契约草案以原型 Architecture 画板上的字段为起点（budget / requirements / scoring / evidence / style_card / siblings）。
4. ADR-A（正文载体分界线）与 ADR-B（大纲即记分卡投影）走 grilling 落 ADR 0009 / 0010。
