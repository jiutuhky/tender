# 02 校验器上移：三脚本逻辑进服务层

Status: resolved
Type: task
Blocked by: 01

## Parent

`.scratch/structured-assets-mcp/PRD.md`（契约：hagent spec §4）

## What to build

把 `bid-response-matrix` skill 三个脚本的确定性逻辑移植为 `src/hagent/assets/validators.py`：结构校验（原 `validate_response_matrix.py`）、组装一致性（原 `assemble_matrix.py` 的 id 唯一/区段合法性/meta 类型冲突检查）、源文保真（原 `verify_source_fidelity.py`，经 document registry 解析 workspace 路径按 line_span 比对字面重叠）。输出统一为结构化报告：每条错误带 target/code/message/修复建议。publish 门禁调用全套；`validate` 可单独跑。

## Acceptance criteria

- [x] 三校验器对原脚本的测试语料给出一致判定（pass/error 集合等价；报错定位从 chunk_file:line 换算为 matrix/item_id）
- [x] 保真校验失败项报告含源 span 摘录与建议操作（update line_span / 拆分条目），与原脚本修复指引等价
- [x] 校验为纯读：跑校验不产生任何对象库写入与审计事件
- [x] 原脚本暂不删除（05 票处理），但服务层不再调用它们

## Comments

2026-07-13（实现，agent）：落地为 `hagent/src/hagent/assets/validators.py`（三校验器 + 结构化报告 + publish 门禁），服务层新增 `AssetService.validate_matrix`（纯读单独跑）与 `AssetService.publish_gate`（构造 `publish(validate=...)` 接缝的全套门禁闭包）。测试 `tests/assets/test_validators{,_parity}.py` + `test_validate_and_publish_gate.py`（全仓 1092 passed）。实现期决策：

- **等价性用真基准锁死**：parity 测试以 subprocess 跑原三脚本，同一语料生成文件/对象两种形态，比对错误集合（保真轴精确到 (matrix, item, code)，coverage 分值逐位一致——评分函数逐字移植）。原脚本删除（票 05）后 parity 测试随 skipif 整体跳过，行为基准由直接断言测试（test_validators.py）延续。
- **校验面裁剪**：`schema_version` / `generated_at` / `source_documents` 已由服务层与 document registry 接管，不再属于 meta 校验面；文件流水线机械检查（done 文件、chunk 行格式、merge_plan 操作）随 S4 工具化退场，一致性校验只上移 id 唯一 / 区段合法 / meta 类型冲突三类。basic_info 的 `project.packages` 已行化，从 meta.project 的警告键清单中移除。
- 新模型独有检查：`id_mismatch`（payload.id 与行 item_id 不一致）与 `missing_meta_field`（信封键缺失即错，原脚本靠 skeleton 恒过此检）。原 `source_file_decode_error` 并入 `source_file_missing`（同一修复动作）。
- 双轴评审回修：`extraction_summary` 显式 null 与 basic_info `meta.project` 缺失/null 均判 error（对齐原脚本 `isinstance(dict)` 语义，首版误放行）。门禁强制性遗留（服务层 `publish(validate=None)` 仍是可绕过的接缝）按 spec §5 归票 03 落实，已补进其验收清单。
- 门禁文档快照在进入 publish 事务前取好（`publish_gate` 自有事务），避免门禁回调在 publish 事务内再开 SQLite 连接。
- 跨矩阵一致性（project_name/project_id 不一致告警）上移为 `cross_matrix_issues`，供票 03 `prose_validate_matrix(all)` 聚合用。
