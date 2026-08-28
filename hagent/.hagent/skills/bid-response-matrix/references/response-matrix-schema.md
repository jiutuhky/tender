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

`compliance_overview.qualification_review` / `compliance_overview.conformity_review` / `compliance_overview.invalid_bid_triggers` 区段收录审查清单与废标情形记录，形状同原文条目（文本 + `source_refs`）。

## technical

`items` 记录形状（必填字段同 business）：

```json
{
  "id": "TECH-001",
  "category": "function",
  "title": "知识解析能力",
  "requirement_text": "",
  "mandatory": false,
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

`evaluation.pass_fail_rules` 与 `evaluation.tie_break_rules` 区段收录通过/淘汰规则与平局裁决记录（文本 + `source_refs`）。

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
