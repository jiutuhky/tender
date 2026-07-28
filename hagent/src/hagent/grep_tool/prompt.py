"""Prompt constants for the Grep / Glob tools (aligned with Claude Code)."""

GREP_TOOL_NAME = "Grep"
GLOB_TOOL_NAME = "Glob"

GREP_TOOL_DESCRIPTION = """A powerful search tool built on ripgrep.

Usage:
- ALWAYS use Grep for content search. NEVER invoke `grep` or `rg` through the Bash
  tool — the Grep tool is optimized for correct permissions and output formatting.
- Supports full regular-expression syntax (e.g. "log.*Error", "function\\s+\\w+").
  Patterns use ripgrep syntax (not POSIX grep); literal braces must be escaped
  (use `interface\\{\\}` to find `interface{}` in Go code).
- Filter the files searched with `glob` (e.g. "*.js", "**/*.tsx") or `type`
  (e.g. "js", "py", "rust", "md").
- `output_mode` controls what is returned:
  - "files_with_matches" (default): file paths that contain a match.
  - "content": the matching lines themselves; honors `-n`, `-A`, `-B`, `-C`.
  - "count": match counts per file.
- `-i` enables case-insensitive matching. `-n` prepends line numbers in content
  mode. `-A`/`-B`/`-C` add lines of context after/before/around each match
  (content mode only).
- `multiline` lets a single pattern span lines (`.` matches newlines). Default off:
  patterns match within one line.
- `head_limit` caps the number of output lines/entries returned.
- For open-ended searches that need several rounds, dispatch the Agent tool with
  subagent_type "Explore" instead."""

GLOB_TOOL_DESCRIPTION = """Fast file-pattern matching tool that works with any codebase size.

- Supports glob patterns like "**/*.js", "src/**/*.ts", or "*.md".
- Returns matching file paths sorted by modification time (most recent first).
- `path` scopes the search to a directory (defaults to the workspace root).
- Use this when you need to find files by name or path shape. Prefer it over
  `find`/`ls` through the Bash tool. For open-ended searches that need several
  rounds, dispatch the Agent tool (subagent_type "Explore") instead."""
