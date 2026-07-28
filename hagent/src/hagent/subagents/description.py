from __future__ import annotations

from typing import Sequence

from hagent.subagents.types import SubagentSpec


def _render_agent_listing(specs: Sequence[SubagentSpec]) -> str:
    if not specs:
        return "(no subagents available)"
    return "\n".join(f"- {s['name']}: {s['description']}" for s in specs)


def render_agent_tool_description(specs: Sequence[SubagentSpec]) -> str:
    listing = _render_agent_listing(specs)
    return f"""Launch a new subagent to handle a complex, multi-step task in an isolated context window.

Available agent types and the tools they have access to:
{listing}

When using the Agent tool, specify a `subagent_type` to select which agent to use. If omitted, the general-purpose agent is used by default. Put the full task brief in the `prompt` parameter — the subagent only sees that string. Use `description` for a short 3-5 word label.

When NOT to use the Agent tool:
- If you want to read a specific file path, use Read directly — that is faster than spawning a subagent.
- If you are searching for a specific symbol in a single file or a small set (2-3 files), use Read directly.
- If the task is trivial (a few tool calls) and delegation would not reduce context usage.
- If you need to observe the subagent's intermediate steps — the Agent tool hides them.

Usage notes:
- Always provide a self-contained brief in `prompt`. The subagent does not see the parent conversation; describe what to do, what's already known, what's in/out of scope.
- For pure lookups, hand over the exact command or keywords. For investigations, hand over the question and let the subagent decide the steps.
- Launch multiple subagents concurrently when the work is independent — use a single message with multiple Agent tool calls.
- When the subagent finishes, it returns a single message back to you. The user does not see that result directly; summarise it for them.
- The subagent's findings are generally trustworthy; you do not need to redo its work to verify unless it reports failure or low confidence.
- Clearly state whether the subagent should write code, run analysis, or only research — it does not know the user's intent.

Example usage:

<example>
User: "Where is the SSE writer defined?"
Assistant: <thinking>Single-shot lookup — Explore can answer this without polluting my context.</thinking>
Calls Agent(description="locate SSE writer", prompt="Find where the SSE writer is defined in src/hagent/server. Return file paths and the symbol names. Quick search.", subagent_type="Explore")
</example>

<example>
User: "Plan a refactor that splits backends.py into per-backend modules."
Assistant: Calls Agent(description="plan backend split", prompt="Design how to split src/hagent/backends.py into one module per backend class. List the steps, the new file layout, and the migration risks. Include a 'Critical Files' section at the end.", subagent_type="Plan")
</example>"""
