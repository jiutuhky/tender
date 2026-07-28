"""JSON-Schema definitions for the Grep / Glob tools.

These are hand-written JSON Schemas (not pydantic models) so that the property
names exposed to the model match Claude Code's Grep tool exactly — including the
dash-flag keys ``-i`` / ``-n`` / ``-A`` / ``-B`` / ``-C``. LangChain converts a
pydantic ``args_schema`` with ``by_alias=False``, which would surface the Python
field names instead of the aliases; a raw schema dict avoids that and reaches the
model verbatim.
"""

from __future__ import annotations

# Valid keys accepted by the Grep tool. Anything else is rejected (mirrors CC's
# additionalProperties: false), validated explicitly in the tool function.
GREP_ALLOWED_KEYS = frozenset(
    {"pattern", "path", "glob", "type", "output_mode", "-i", "-n", "-A", "-B", "-C", "multiline", "head_limit"}
)

GREP_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["pattern"],
    "properties": {
        "pattern": {
            "type": "string",
            "description": "The regular expression pattern to search for in file contents (ripgrep syntax).",
        },
        "path": {
            "type": "string",
            "description": "File or directory to search in (defaults to the workspace root).",
        },
        "glob": {
            "type": "string",
            "description": 'Glob pattern to filter files (e.g. "*.js", "**/*.tsx"). Mutually useful with type.',
        },
        "type": {
            "type": "string",
            "description": 'File type to search (e.g. "js", "py", "rust", "go", "md"). More efficient than glob for standard types.',
        },
        "output_mode": {
            "type": "string",
            "enum": ["content", "files_with_matches", "count"],
            "description": 'Output mode: "content" shows matching lines (supports -n/-A/-B/-C), "files_with_matches" shows file paths (default), "count" shows match counts.',
        },
        "-i": {
            "type": "boolean",
            "description": "Case-insensitive search.",
        },
        "-n": {
            "type": "boolean",
            "description": "Show line numbers in output (content mode only).",
        },
        "-A": {
            "type": "integer",
            "description": "Number of lines to show after each match (content mode only).",
        },
        "-B": {
            "type": "integer",
            "description": "Number of lines to show before each match (content mode only).",
        },
        "-C": {
            "type": "integer",
            "description": "Number of lines to show before and after each match (content mode only).",
        },
        "multiline": {
            "type": "boolean",
            "description": "Enable multiline mode where . matches newlines and patterns can span lines (default false).",
        },
        "head_limit": {
            "type": "integer",
            "description": "Limit output to the first N lines/entries.",
        },
    },
}

GLOB_ALLOWED_KEYS = frozenset({"pattern", "path"})

GLOB_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["pattern"],
    "properties": {
        "pattern": {
            "type": "string",
            "description": 'The glob pattern to match files against (e.g. "**/*.js", "src/**/*.ts").',
        },
        "path": {
            "type": "string",
            "description": "The directory to search in (defaults to the workspace root).",
        },
    },
}
