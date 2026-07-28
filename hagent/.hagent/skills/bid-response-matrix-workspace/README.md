# bid-response-matrix eval 工作区

对新版（工具化编排）skill 的评测流程，承接原 `extract-tech-requirements-workspace` 的
真实语料与断言口径：产物从「五个 JSON 文件」换成对象库里的四个应答矩阵，打分改读
SQLite（`grade.py`）。

## 语料

三份真实招标文件（MinerU 抽取的 Markdown），路径见各 `evals/eval-*/eval_metadata.json`
的 `source_md`（仓根 `data/` 下）。

## 跑一次 eval

```bash
cd hagent && source .venv/bin/activate
set -a && source .env && set +a

# 1. 环境：独立 DB + workspace，skill 走仓内 .hagent/skills
export HAGENT_SESSIONS_DB=/tmp/hagent-eval/sessions.db
export HAGENT_WORKSPACE_ROOT=/tmp/hagent-eval/workspaces
export HAGENT_SKILLS_PATHS="$PWD/.hagent/skills"
PROJECT=eval-0-sim   # 用 eval 目录名作 project_id

# 2. 语料入 workspace（新流程要求源文件在 project workspace 内注册）
WS="$HAGENT_WORKSPACE_ROOT/projects/$PROJECT/workspace"
mkdir -p "$WS/docs" && cp "<eval_metadata.source_md>" "$WS/docs/tender.md"

# 3. 运行（prompt 取自 eval_metadata.json，含 project_id 与 workspace 相对路径）
python -m hagent demo --skill bid-response-matrix "<eval_metadata.prompt>"

# 4. 打分（读对象库 + 原文，写 grading.json）
python .hagent/skills/bid-response-matrix-workspace/grade.py \
  "$HAGENT_SESSIONS_DB" "$PROJECT" <doc_key> "<eval_metadata.source_md>"
```

`grade.py` 断言三大维度（与原 eval 口径对齐）：schema/发布状态（四矩阵 published、
全套校验 pass）、信息完整性（资格/符合性/技术/商务条数下限、评分合计与维度拆分）、
忠于原文（预算、项目编号、mandatory 信号、requirement_text 直读源文抽样命中）。
阈值以 `grade.py` 的 `EXPECTED` 为权威；`eval_metadata.json` 的 `assertions`
是给评审人读的镜像，改阈值两处同步。

对照组（without_skill）：同一 prompt 去掉 `--skill` 直接跑，其余步骤不变。
