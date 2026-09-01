# Response Matrix Schema（应答矩阵数据契约）

应答矩阵的唯一事实来源是 Prose 对象库；本文件是向对象库提交与修复记录时的形状契约，同一份内容也以 MCP resource `prose://contracts/matrix-schema` 镜像发布。宁可 `null`、空数组加 `notes` 说明，也不要编造值。

每个矩阵由两部分组成：

- **meta（envelope）**——经 `prose_set_matrix_meta` 维护的固定标量结构。
- **区段记录（rows）**——经 `prose_submit_matrix_records` 按区段提交的条目行；各矩阵可用区段见工具 schema。

`response_status`、`response_note`、`confirmed` 是发布后的人工状态，由专门工具管理，绝不出现在记录 payload 里。

## 公共 envelope

每个矩阵的 meta 必须含：

```json
{
  "project_id": null,
  "project_name": null,
  "extraction_summary": {
    "status": "complete",
    "confidence": "medium",
    "warnings": []
  }
}
```

字段规则：

- `project_id`：稳定 slug 或招标编号，没有则 `null`。
- `project_name`：完整项目名，没有则 `null`。
- `extraction_summary.status`：`complete` / `partial` / `needs_review`。
- `extraction_summary.confidence`：`high` / `medium` / `low`。
- `schema_version`、`generated_at`、`source_documents` 由服务端与 document registry 接管，不要提交。

## Source Reference

每条抽取记录都带 `source_refs`：

```json
{
  "document_id": "doc-a1b2c3d4",
  "line_span": [120, 138],
  "section": "投标人须知前附表"
}
```

规则：

- `document_id` 必须是 `prose_register_document` 返回的已注册 doc_id。
- `line_span` 为 1 起始闭区间 Markdown 行号 `[start_line, end_line]`。
- 一条记录由多段不连续原文支撑时用多条 ref。
- 不要包含 `quote` 或 `locator`；源文摘录由 `document_id` + `line_span` 复原。

## basic_info

meta 在公共 envelope 外增加 `project` 标量结构（`packages` 走区段行，不进 meta）：

```json
{
  "project": {
    "name": null,
    "number": null,
    "procurement_method": null,
    "evaluation_method": null,
    "purchaser": { "name": null, "contact": null, "phone": null, "address": null },
    "agency": { "name": null, "contact": null, "phone": null, "address": null },
    "budget": { "amount": null, "currency": "CNY", "text": null },
    "scope": null,
    "delivery_or_service_period": null,
    "delivery_location": null
  }
}
```

区段记录形状：

`project.packages` 记录：

```json
{
  "package_id": null,
  "package_name": null,
  "budget": { "amount": null, "currency": "CNY", "text": null },
  "scope": null,
  "source_refs": []
}
```

`timeline` 记录：

```json
{
  "event": "bid_deadline",
  "datetime": null,
  "timezone": null,
  "location": null,
  "source_refs": []
}
```

`contacts` 记录为联系人对象（姓名/角色/电话等，按原文取字段）；`source_refs` 区段收录项目级引用。

## business

`items` 记录形状（`id`、`category`、`title`、`requirement_text`、`mandatory`、`response_required`、`source_refs`、`confidence` 为必填）：

```json
{
  "id": "BIZ-001",
  "category": "qualification",
  "title": "供应商资格要求",
  "requirement_text": "",
  "mandatory": true,
  "param_nature": "★",
  "response_required": true,
  "evidence_required": [],
  "deadline_or_period": null,
  "related_forms": [],
  "risk_level": "high",
  "source_refs": [],
  "confidence": "high",
  "notes": null
}
```

推荐 `category`：`qualification`、`conformity`、`bid_document`、`pricing`、`guarantee`、`contract`、`payment`、`delivery`、`acceptance`、`confidentiality`、`service`、`invalid_bid`、`other`。

`param_nature`（可选，`"★"` / `"▲"` / `null`）：要求表「参数性质」列的原文符号，照录不翻译。OCR 变体先归一（`*`、`☆` → `★`；`△`、`Δ` → `▲`），列为空或无此列置 `null`（一般条款）。它与 `mandatory` 双写而非互斥：

- `★` 是实质性条款（负偏离即无效投标）⇒ 同时置 `mandatory: true`；
- `▲` 是重要参数（负偏离扣分更重、影响响应性评审，但**不废标**）⇒ 置 `mandatory: false`，除非同条款另有无效投标措辞；
- 两者不一致时校验报 warning，交主 agent 对照原文裁决。

存量抽取无此字段，故不列入必填。

`compliance_overview.qualification_review` / `compliance_overview.conformity_review` / `compliance_overview.invalid_bid_triggers` 区段收录审查清单与废标情形记录，形状同原文条目（文本 + `source_refs`）。行可另带可选 `response_format`（字符串或 `null`）——符合性/资格审查表「响应格式」列的原文，指明该审查项在投标文件里的应答位置。

## technical

`items` 记录形状（必填字段同 business）：

```json
{
  "id": "TECH-001",
  "category": "function",
  "title": "知识解析能力",
  "requirement_text": "",
  "mandatory": false,
  "param_nature": "▲",
  "response_required": true,
  "evidence_required": [],
  "acceptance_criteria": [],
  "related_deliverables": [],
  "source_refs": [],
  "confidence": "high",
  "notes": null
}
```

推荐 `category`：`scope`、`function`、`performance`、`architecture`、`environment`、`security`、`data`、`integration`、`testing`、`deliverable`、`acceptance`、`training`、`maintenance`、`service`、`other`。

`param_nature` 同 business 段的规则（技术要求表的「参数性质」列是它的主要来源）。★/▲ 的计分后果不写在这里——加扣分、封顶、熔断规则归 scoring 的 `evaluation.deviation_rules`。

`deliverables` 与 `acceptance_requirements` 区段收录交付物与验收要求记录（文本 + `source_refs`）。

## scoring

meta 在公共 envelope 外增加 `evaluation` 标量结构（`pass_fail_rules` / `tie_break_rules` 走区段行，不进 meta）：

```json
{
  "evaluation": {
    "method": null,
    "total_score": null,
    "price_score": null,
    "business_score": null,
    "technical_score": null
  }
}
```

`items` 记录形状（`id`、`group`、`title`、`max_score`、`scoring_rule`、`scoring_method`、`source_refs`、`confidence` 为必填；`max_score` 是数字或 `null`）：

```json
{
  "id": "SCORE-001",
  "group": "technical",
  "subgroup": "技术方案",
  "title": "技术方案评分",
  "max_score": null,
  "scoring_rule": "",
  "scoring_method": "subjective",
  "evidence_required": [],
  "related_format": "「技术方案」相关证明材料",
  "related_requirement_ids": [],
  "mandatory_gate": false,
  "source_refs": [],
  "confidence": "high",
  "notes": null
}
```

`group`：`price` / `business` / `technical` / `service` / `policy` / `other`。

`subgroup`（可选，字符串或 `null`）：评审标准表「评审因素分类」列的原文用词（业绩 / 技术方案 / 一般技术指标评审 …），不归一化、不翻译。它是 `group` 之下的二级分类，前端评分详情据此立分组眉；缺省或部分缺省时列表退化为一级项内平铺，不报错。存量抽取无此字段，故不列入必填。

`scoring_method`：`objective` / `subjective` / `formula` / `pass_fail` / `mixed`。

`related_format`（可选，字符串或 `null`）：评审标准表「关联格式」列的原文用词（如 `「技术方案」相关证明材料`、`售后服务方案`、`技术指标参数响应偏离表`），照录不归一化。它是该评分项在投标客户端里的材料挂载位置，决定投标文件的分册组织。表里没有这一列时置 `null`。

`evaluation.pass_fail_rules` 与 `evaluation.tie_break_rules` 区段收录通过/淘汰规则与平局裁决记录（文本 + `source_refs`）。

### evaluation.deviation_rules

偏离计分规则区段：技术指标正/负偏离的加扣分、封顶与熔断清零。每条规则一行：

```json
{
  "id": "DEVR-001",
  "direction": "negative",
  "applies_to": ["▲"],
  "delta_per_item": 0.3,
  "cap": null,
  "threshold_items": null,
  "effect_text": null,
  "rule_text": "",
  "source_refs": [],
  "notes": null
}
```

字段规则：

- `direction`（必填）：`positive` 正偏离加分 / `negative` 负偏离扣分 / `zero_out` 达到项数后清零。
- `applies_to`：适用的参数档，`["★"]` / `["▲"]` / `["general"]`（列为空的一般参数）的组合；规则不分档、对全部参数一视同仁时置 `null`。
- `delta_per_item`：每项加或扣的分值，**绝对值**（加扣方向由 `direction` 表达，不要写负号）。
- `cap`：该规则累计加/扣分的封顶（绝对值），无封顶置 `null`。
- `threshold_items`：仅 `zero_out` 使用——触发清零所需的偏离项数。
- `effect_text`：清零后果的原文短语（各文件差异大：有的清零「技术指标部分得分」，有的清零「技术评审总得分」），照录原文，其余情况置 `null`。
- `rule_text`（必填）：规则原文措辞，解读进 `notes`。
- `source_refs`（必填非空）：同全局规则。

原文没有明确数字时把数字字段留 `null`，规则原文照样落进 `rule_text`——宁可缺结构化字段，不要编造分值。

**边界**：`★ 条款负偏离即无效投标` 属于废标规则，进 `evaluation.pass_fail_rules`，**不重复**进本区段；本区段只收计分性后果（加分、扣分、清零）。

三种真实形态示例（省略 `rule_text` / `source_refs`）：

```json
{"direction": "positive", "applies_to": null, "delta_per_item": 2, "cap": 10}
{"direction": "negative", "applies_to": ["▲"], "delta_per_item": 0.3, "cap": null}
{"direction": "zero_out", "applies_to": null, "threshold_items": 3,
 "effect_text": "技术指标评审总得分为0分"}
```

## unresolved_items

四个矩阵都有 `unresolved_items` 区段，收录抽取中无法裁决的问题：

```json
{
  "id": "UNRESOLVED-001",
  "severity": "medium",
  "issue": "两份文件交付期冲突",
  "source_refs": [],
  "recommended_review": "确认哪份文件优先。"
}
```

`severity`：`high` / `medium` / `low`。
