# 抽取 Pass 指南

一次抽取 pass 对一套招标文件抽取恰好一个矩阵类型——`basic_info`、`business`、`technical` 或 `scoring`。无论 pass 以并发 subagent 还是主 agent 顺序自跑的形式执行，本指南一字不差同样适用。严格照做：即兴发挥的格式与口径过不了服务端校验。

## 输入

你的 prompt 会给出：目标矩阵类型、project_id、各 doc_id 与对应源文件路径、数据契约（response-matrix-schema）的路径。动手前先通读本文件，再读契约里你目标矩阵的章节。

只从已注册的 OCR 规范化 Markdown 抽取，且只读你的矩阵需要的文档。同一事项既有通用法律样板又有项目专用章节时，以专用章节为准：中文采购文件里 `专用文件`、`投标人须知前附表`、`采购需求`、`技术要求`、`评审标准` 通常覆盖通用条款。

## 源文保真

- 每个抽取条目都带指向原文的 `source_refs`（形状与行号规则见数据契约的 Source Reference 章节）；一个条目由多段不连续原文支撑时用多条 ref。
- 抽取文本字段（`requirement_text` 或 `scoring_rule`）贴住原文措辞——后续校验会度量该字段与所引 span 的字面重叠度，转述过不了。解释、归一化、保留意见一律进 `notes`，绝不进抽取文本。
- OCR、公式转换或表格提取有降级时照常抽取，同时提交一条 `unresolved_items` 记录。

## 分类

- `basic_info`：标识项目、包件、当事方、金额、日程、地点、采购方式或联系人。
- `business`：约束投标人资格、投标文件、签字盖章、保证金担保、报价、付款、合同、保密、作为商务义务的交付、验收程序、售后服务、无效投标情形或符合性审查。
- `technical`：描述须建设、交付、配置、集成、测试、加固、部署、培训、维护或作为技术交付物验收的内容。
- `scoring`：影响评审、分值、公式、排名、通过/淘汰门槛、价格分、平局裁决或评分证明材料，以及偏离的计分后果（加分、扣分、清零规则）。

只抽属于你矩阵的内容。一条条款横跨多个矩阵时，取你矩阵所需的最小表示，其余经 `related_requirement_ids` 或 `notes` 交叉引用。

## Mandatory 信号

原文出现下列信号时置 `mandatory: true`（scoring 条目为 `mandatory_gate: true`）：

- `★`、`*`、`必须`、`须`、`应当`、`不得`、`不允许负偏离`
- `否则视为无效投标`、`无效投标`、`不得进入后续评审`
- `资格性审查`、`符合性审查`、`实质性响应`
- 明示的通过/淘汰计分或其他硬性合规措辞

可导致废标的 business 条目置 `risk_level: "high"`。

**参数性质另立字段**：商务/技术要求表常有「参数性质」列，标 `★`（实质性）、`▲`（重要）或留空（一般）。该列的原文符号落进 `param_nature`（变体先归一：`*`、`☆` → `★`；`△`、`Δ` → `▲`；列空置 `null`），同时按下面的对应关系置 `mandatory`：

- `★` ⇒ `param_nature: "★"` + `mandatory: true`。
- **`▲` 不是 mandatory 信号** ⇒ `param_nature: "▲"` + `mandatory: false`。▲ 条款负偏离扣分更重、影响响应性评审，但**不导致无效投标**；只有同条款另有明示的废标措辞时才置 `mandatory: true`。
- 列为空 ⇒ `param_nature: null`，`mandatory` 照常按上面的信号清单判定。

▲ 的扣分幅度不写进条目——它属于 scoring 的 `evaluation.deviation_rules`。

## 粒度

- 大段落拆成原子需求：以「投标人需要分别应答或分别举证」为拆分标准。
- 紧耦合的子条款保持在一起：拆开会丢上下文的不拆。
- 避免碎到标书编写者无从下手的片段。

## 评分专项

仅 `scoring` pass 适用：

- 评分表每一行都是一条独立的 `items` 记录，绝不揉成一段散文概括。
- 保留满分、分组、计分方式、公式与证明材料要求。
- `subgroup` 记评审标准表「评审因素分类」列的原文用词（业绩 / 企业规模 / 财务状况 / 技术力量 / 技术方案 / 一般技术指标评审 / 培训和售后服务 …），不归一化、不翻译、不自造分类。该列在表中常以合并单元格跨若干行，跨到的每一行都要各自带上同一个值。表里确实没有这一列时置 `null`——宁可留空，不要凭 `title` 猜一个。
- 表内分值合计可算时与宣称总分核对，不一致记为 warning。
- 主观分档保留原文阈值措辞，解读进 `notes`。
- 评审标准表有「关联格式」列时，逐行照录进 `related_format`——它指明该评分项的材料挂载位置，决定投标文件分册，丢了投标人就不知道材料该放哪。
- **偏离计分规则单独成行**：正偏离加分、负偏离扣分、加扣分封顶、负偏离达 N 项清零这类规则，不要揉进任何评分项的 `scoring_rule`，抽进 `evaluation.deviation_rules` 区段。每个方向一行；规则按 ★/▲/一般分档给出不同幅度时，每档各一行。数字进 `delta_per_item` / `cap` / `threshold_items`（一律绝对值），规则原文进 `rule_text`，清零后果的原文短语进 `effect_text`。
- `★ 条款负偏离即无效投标` 是废标规则，进 `evaluation.pass_fail_rules`，不重复进 `deviation_rules`。

## 冲突与不确定性

- 招标文件声明后发修正或专用文件优先时，从其规定。
- 优先级不明时：两处 source_refs 都保留，取保守值，置 `confidence: "low"`，并提交一条 `unresolved_items` 记录。日期、预算、mandatory 标志、分值冲突绝不静默覆盖。
- 凡依赖推断、劣质 OCR 或残缺表格得出的条目，置 `confidence: "low"`。
- 不要虚构投标人应答：矩阵记录招标方要求什么；除非用户提供了投标人事实，应答字段留空。

## 提交

所有产出经 `prose_submit_matrix_records` 按区段提交进你矩阵的草稿区：

1. 记录形状严格照数据契约里你矩阵的章节。
2. envelope（project_id、project_name、extraction_summary，以及 basic_info 的 `project`、scoring 的 `evaluation` 标量）经 `prose_set_matrix_meta` 设置。
3. 不确定与降级事项作为 `unresolved_items` 区段的记录提交。

你的交付物是草稿区里的记录，不是文字总结。

## 完成

提交完成前，对照本清单把源文档从头到尾扫一遍；任何一条不满足，pass 就没结束：

- 与你矩阵相关的每个文档章节，要么产出了记录，要么被明确排除——从首行到末行逐标题走完，不跳章节。
- 落在你范围内、带 mandatory 信号（见上）的每一条款，都以条目或 `unresolved_items` 记录呈现。
- business / technical pass：要求表有「参数性质」列时，★ 与 ▲ 已逐行落进 `param_nature`，且与 `mandatory` 的对应关系符合上面的规则。
- scoring pass：评分表每一行都成了条目，且可算合计与宣称总分核对过；「关联格式」列已落 `related_format`；评分办法里的偏离加扣分、封顶、熔断规则已落 `evaluation.deviation_rules`，没有被并进某个评分项的 `scoring_rule` 里。

然后用 `prose_validate_matrix` 校验你的矩阵，照每条 issue 的 hint 修复并重跑，直到没有 error。最后向主 agent 简短汇报：各区段提交计数、低置信条目与 `unresolved_items` 要点。
