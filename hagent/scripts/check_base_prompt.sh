#!/usr/bin/env bash
set -euo pipefail

PROMPT="prompts/hagent_base.zh.md"
DEC="prompts/decisions.md"

if [[ ! -f "$PROMPT" ]]; then
    echo "FAIL: $PROMPT not found"
    exit 1
fi
if [[ ! -f "$DEC" ]]; then
    echo "FAIL: $DEC not found"
    exit 1
fi

# 禁用词检查；base prompt 不允许残留 Claude Code 来源标识
for term in "Claude Code" "Anthropic" "Claude Opus" "claude-opus-"; do
    if grep -q "$term" "$PROMPT"; then
        echo "FAIL: prohibited provenance term '$term' found in $PROMPT"
        grep -n "$term" "$PROMPT" || true
        exit 1
    fi
done

# 文件工具名映射应该已替换；Task tools 是当前任务规划工具名，允许并要求出现
for old in " Bash " " Edit " " Read " " Write "; do
    if grep -q "$old" "$PROMPT"; then
        echo "WARN: old tool name '$old' (with spaces) found in $PROMPT — verify mapping was applied"
        grep -n "$old" "$PROMPT" || true
    fi
done

for tool in "TaskCreate" "TaskGet" "TaskUpdate" "TaskList"; do
    if ! grep -q "$tool" "$PROMPT"; then
        echo "FAIL: $PROMPT missing required Task tool '$tool'"
        exit 1
    fi
done

if grep -q "write_todos" "$PROMPT"; then
    echo "FAIL: $PROMPT still mentions disabled write_todos tool"
    grep -n "write_todos" "$PROMPT" || true
    exit 1
fi

# decisions.md 必须覆盖关键标题
for section in "开头身份段" "IMPORTANT" "# System" "# Doing tasks" "# Executing actions" "# Using your tools" "# Tone and style" "# auto memory" "# Environment" "# Context management" "# Session-specific" "# Tools"; do
    if ! grep -q "$section" "$DEC"; then
        echo "FAIL: $DEC missing coverage of section '$section'"
        exit 1
    fi
done

# tiktoken 计数报告应该在 decisions.md 末尾
if ! grep -qi "tiktoken" "$DEC"; then
    echo "FAIL: $DEC missing tiktoken token count report"
    exit 1
fi

echo "OK: scaffold checks passed"
