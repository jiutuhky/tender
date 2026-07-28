# Hagent Hooks 使用指南

Hagent 移植了 Claude Code 的 hook 机制：在工具调用前后、prompt 提交、会话生命周期、agent 停止等时机执行你配置的命令，用于阻断危险操作、注入上下文、驱动外部校验等。配置 schema 与 Claude Code 完全同构，CC 的 hooks 配置可直接拷贝。

> 设计契约与 CC 对齐细节见 `docs/specs/2026-07-06-hagent-hooks-design.md`。

## 配置位置

三层合并，越靠后优先级越高（同 hook 去重时后加载层胜出）：

1. `~/.hagent/settings.json`（用户级）
2. `<项目根>/.hagent/settings.json`（项目级；项目根 = server 进程 CWD）
3. `<项目根>/.hagent/settings.local.json`（本地覆盖，建议加入 .gitignore）

配置在 **session 创建时快照**：修改 settings 后需新建 session 才生效。

环境变量：

| 变量 | 作用 |
| --- | --- |
| `HAGENT_HOOKS_DISABLED=1` | 全局禁用 hooks |
| `HAGENT_HOOKS_SETTINGS_PATHS=/a.json,/b.json` | 替换默认发现路径（逗号分隔） |
| `HAGENT_HOOKS_READ_CLAUDE_SETTINGS=1` | 额外读 `~/.claude/settings.json` 与项目 `.claude/settings.json`（最低优先级，默认关） |
| `HAGENT_HOOKS_SMALL_MODEL` | prompt/agent 型 hook 的默认模型（缺省 Haiku） |

## 基本结构

```json
{
  "hooks": {
    "<事件名>": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "your-hook.sh", "timeout": 10 }
        ]
      }
    ]
  }
}
```

### matcher 规则

- 缺省或 `*`：全匹配
- `Write|Edit`：按 `|` 分割精确匹配（大小写敏感）
- 其他：按正则处理（如 `mcp__.*`）；非法正则按不匹配

各事件的匹配维度：工具类事件 = `tool_name`；SessionStart = `source`；SessionEnd = `reason`；SubagentStart/SubagentStop = `agent_type`。**Stop / UserPromptSubmit 没有匹配维度，matcher 被忽略。**

### hook 类型

| type | 行为 | 默认超时 |
| --- | --- | --- |
| `command` | 执行 shell 命令，事件 JSON 从 stdin 传入 | 600s（SessionEnd 1.5s） |
| `http` | POST 事件 JSON 到 `url`，响应体按输出 JSON 解析 | 600s |
| `prompt` | 用小模型对 `prompt` 求值，返回 ok/不 ok（`$ARGUMENTS` 占位输入 JSON） | 30s |
| `agent` | 带 Read/Grep/Glob 只读工具的验证 agent，结论同 prompt 型 | 60s |

通用字段：`timeout`（秒）、`once`（本 session 只跑一次）、`async`（后台执行不阻塞，输出忽略）。同一事件命中的多个 hook **并行执行**。

## 支持的事件

| 事件 | 时机 | 阻断（exit 2）效果 |
| --- | --- | --- |
| `PreToolUse` | 工具执行前 | 拒绝该次工具调用，stderr 给模型 |
| `PostToolUse` | 工具成功后 | stderr 作为反馈附给模型（工具已执行） |
| `PostToolUseFailure` | 工具失败后 | —（观测 + additionalContext） |
| `UserPromptSubmit` | 用户消息进图前 | 擦除 prompt，SSE 返回 `hook.blocked` 事件 |
| `Stop` | 模型即将结束回复 | 阻止停止，stderr 作为新用户消息让模型继续 |
| `SubagentStart` / `SubagentStop` | 子代理启动/停止 | Start 阻断被忽略；Stop 同主图 Stop |
| `SessionStart` | POST /sessions 创建后 | 阻断被忽略 |
| `SessionEnd` | DELETE /sessions 前 | 输出全忽略（1.5s 超时兜底） |
| `PermissionDenied` | PreToolUse hook deny 后 | —（观测） |

其余 CC 事件名（PreCompact、Notification 等）schema 层可识别，配置后会记 warning 但不会触发。

## command hook 怎么写

stdin 收到事件 JSON：公共字段 `session_id` / `transcript_path` / `cwd` / `hook_event_name`（子代理内触发时另有 `agent_id` / `agent_type`），加事件专属字段（如 PreToolUse 的 `tool_name` / `tool_input` / `tool_use_id`，UserPromptSubmit 的 `prompt`，Stop 的 `stop_hook_active` / `last_assistant_message`）。env 注入 `CLAUDE_PROJECT_DIR`（项目根）。

### 用 exit code 控制

- **exit 0**：放行。stdout 在 UserPromptSubmit / SessionStart / SubagentStart 会注入给模型作上下文，其他事件忽略。
- **exit 2**：阻断（效果见上表），stderr 作为阻断原因。
- **其他非零**：仅记录 warning，不阻断。

### 用 stdout JSON 精细控制

stdout 是合法 JSON 时按 JSON 语义处理（**此时 exit code 不再起阻断作用**）：

```json
{
  "continue": true,
  "stopReason": "continue=false 时展示的原因",
  "suppressOutput": false,
  "decision": "approve | block",
  "reason": "决策原因",
  "systemMessage": "给用户的警告",
  "hookSpecificOutput": { "hookEventName": "<事件名>", "...": "事件专属字段" }
}
```

`hookSpecificOutput` 事件专属字段：

- **PreToolUse**：`permissionDecision`（`allow` / `deny` / `ask`，多 hook 聚合优先级 deny > ask > allow）、`permissionDecisionReason`、`updatedInput`（改写工具参数）、`additionalContext`
- **PostToolUse / PostToolUseFailure / UserPromptSubmit / SubagentStart**：`additionalContext`
- **SessionStart**：`additionalContext`（注入首条消息）、`initialUserMessage`（随创建响应体返回给前端）

### 示例：拦截危险 Bash 命令

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/.hagent/hooks/guard.sh" }] }
    ]
  }
}
```

```bash
#!/usr/bin/env bash
# .hagent/hooks/guard.sh
input=$(cat)
cmd=$(echo "$input" | jq -r '.tool_input.command // ""')
if [[ "$cmd" == *"rm -rf"* ]]; then
  echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "permissionDecision": "deny", "permissionDecisionReason": "禁止 rm -rf"}}'
fi
exit 0
```

### 示例：Stop 时强制收尾

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [{ "type": "prompt",
        "prompt": "验证代理是否已运行测试且全部通过。$ARGUMENTS" }] }
    ]
  }
}
```

prompt/agent 型 hook 判定不通过时会阻止停止，模型带着原因继续工作。防死循环：Stop payload 里的 `stop_hook_active` 为 true 表示已被阻断过一次（hook 应据此放行）；另有连续阻断 5 次强制放行的硬上限。

## 子代理 frontmatter hooks

markdown agent 文件可声明自己的 hooks（与全局 settings 合并）：

```markdown
---
name: reviewer
description: 代码审查
hooks:
  Stop:
    - hooks:
        - type: command
          command: verify-review.sh
---
```

frontmatter 里的 `Stop` 自动转换为 `SubagentStop`（子代理停止触发的是 SubagentStop）。

## 注意事项

- **hook 永远在宿主执行**（与 CC 一致）。sandbox 模式下 `tool_input` 里是容器内路径，hook 脚本按宿主路径检查会误判，需自行映射。
- `permissionDecision: "ask"` 目前降级为 deny（交互式审批 HITL 尚未接通）。
- `if` 条件字段可解析但暂不求值（按恒真处理）。
- `transcript_path` 指向简版 JSONL（一行一条 user/assistant 消息），与 CC 完整 transcript 格式不对等。
- `tool_response` 可能很大（Bash/Read 输出数百 KB），hook 脚本自行截断。
