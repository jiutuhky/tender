from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

import yaml

from hagent.subagents.types import SubagentSpec

logger = logging.getLogger(__name__)

# 对齐 Claude Code 的 FRONTMATTER_REGEX（src/utils/frontmatterParser.ts）：非贪婪吃到首个 ---，
# 不强求闭合 --- 前有换行。body 用 match.end() 之后的切片取得。
_FRONTMATTER_RE = re.compile(r"^---\s*\n([\s\S]*?)---\s*\n?")
_IGNORED_FRONTMATTER_KEYS = (
    "permissionMode",
    "maxTurns",
    "mcpServers",
    "memory",
    "isolation",
    "background",
    "initialPrompt",
    "requiredMcpServers",
)
_RECOGNIZED_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "tools",
        "disallowedTools",
        "model",
        "color",
        "skills",
        "hooks",
    }
)
_KNOWN_FRONTMATTER_KEYS = _RECOGNIZED_FRONTMATTER_KEYS | set(_IGNORED_FRONTMATTER_KEYS)

# CC quoteProblematicValues：含这些字符的无引号 value 会被加双引号后重试解析。
_YAML_SPECIAL_CHARS = re.compile(r"[{}\[\]*&#!|>%@`]|: ")
# CC 的 key:value 行匹配（仅简单顶层键，不含缩进 / 列表项）。
_CC_KEYVAL_RE = re.compile(r"^([a-zA-Z_-]+):\s+(.+)$")
# 宽松回退用：行首已知键（区分大小写，允许连字符）。
_FM_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$")


def _quote_problematic_values(frontmatter_text: str) -> str:
    """对齐 CC quoteProblematicValues：把含 YAML 特殊字符的无引号单行 value 加双引号。"""
    out: list[str] = []
    for line in frontmatter_text.split("\n"):
        m = _CC_KEYVAL_RE.match(line)
        if m:
            key, value = m.group(1), m.group(2)
            already_quoted = (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            )
            if not already_quoted and _YAML_SPECIAL_CHARS.search(value):
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                out.append(f'{key}: "{escaped}"')
                continue
        out.append(line)
    return "\n".join(out)


def _lenient_frontmatter(frontmatter_text: str) -> dict:
    """宽松回退：按行首已知键切分；伪键行（如 examples 里的 `Context:`）并入上一个键的值。

    用于 CC 插件源文件的「展开」形态——description 无引号、跨真实多行、内嵌 <example>，
    严格 YAML 与 quoteProblematicValues 都解析不了时兜底。
    """
    result: dict[str, str] = {}
    cur_key: str | None = None
    buf: list[str] = []
    for line in frontmatter_text.split("\n"):
        m = _FM_KEY_RE.match(line)
        if m and m.group(1) in _KNOWN_FRONTMATTER_KEYS:
            if cur_key is not None:
                result[cur_key] = "\n".join(buf).strip()
            cur_key = m.group(1)
            buf = [m.group(2).strip()]
        elif cur_key is not None:
            buf.append(line)
    if cur_key is not None:
        result[cur_key] = "\n".join(buf).strip()
    return result


def _parse_frontmatter_dict(raw_fm: str) -> dict | None:
    """三段式解析（对齐 CC + 展开形态兜底）：strict YAML → quoteProblematicValues → 宽松回退。"""
    for text in (raw_fm, _quote_problematic_values(raw_fm)):
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        if isinstance(parsed, dict):
            return parsed
    lenient = _lenient_frontmatter(raw_fm)
    return lenient or None


def _coerce_str_list(value: object) -> list[str] | None:
    """tools / disallowedTools / skills 兼容三种写法：YAML 列表、["a","b"] 串、逗号分隔串。"""
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            parsed = yaml.safe_load(s)
        except yaml.YAMLError:
            parsed = None
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
        return [part.strip() for part in s.split(",") if part.strip()]
    return None


def _parse_one(path: Path) -> SubagentSpec | None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as err:
        logger.warning("failed to read %s: %s", path, err)
        return None

    m = _FRONTMATTER_RE.match(text)
    if not m:
        logger.warning("no YAML frontmatter in %s", path)
        return None
    raw_fm, body = m.group(1), text[m.end():]

    fm = _parse_frontmatter_dict(raw_fm)
    if fm is None:
        logger.warning("invalid YAML frontmatter in %s", path)
        return None

    name = fm.get("name")
    description = fm.get("description")
    if not isinstance(name, str) or not name.strip():
        logger.warning("agent %s missing required 'name'", path)
        return None
    if not isinstance(description, str) or not description.strip():
        logger.warning("agent %s missing required 'description'", path)
        return None

    # 对齐 loadAgentsDir.ts:565：把字面 \n（CC 写盘时转义的换行）还原成真换行。
    description = description.replace("\\n", "\n")

    spec: SubagentSpec = {
        "name": name.strip(),
        "description": description.strip(),
        "system_prompt": body.strip(),
        "source": str(path.parent),
    }
    tools = _coerce_str_list(fm.get("tools"))
    if tools is not None:
        spec["tools"] = tools
    skills = _coerce_str_list(fm.get("skills"))
    if skills is not None:
        spec["skills"] = skills
    disallowed = _coerce_str_list(fm.get("disallowedTools"))
    if disallowed is not None:
        spec["disallowed_tools"] = disallowed
    model = fm.get("model")
    if isinstance(model, str) and model.strip():
        spec["model"] = model.strip()
    color = fm.get("color")
    if isinstance(color, str) and color.strip():
        spec["color"] = color.strip()
    # frontmatter hooks（CC 对齐）：原样保留 dict；Stop→SubagentStop 转换与
    # schema 校验在 hooks 子系统（hagent.hooks.config.load_hooks_dict）做。
    # 宽松回退解析出的字符串形态无法承载嵌套结构，忽略并警告。
    hooks = fm.get("hooks")
    if isinstance(hooks, dict) and hooks:
        spec["hooks"] = hooks
    elif hooks is not None:
        logger.warning("agent %s 的 hooks frontmatter 不是映射结构，忽略", path)

    ignored = [k for k in _IGNORED_FRONTMATTER_KEYS if k in fm]
    if ignored:
        logger.warning(
            "agent %s declares unsupported keys %s; ignored in this release",
            path,
            ignored,
        )
    unknown = sorted(
        set(fm)
        - _RECOGNIZED_FRONTMATTER_KEYS
        - set(_IGNORED_FRONTMATTER_KEYS)
    )
    if unknown:
        logger.warning(
            "agent %s has unknown frontmatter keys %s; ignored",
            path,
            unknown,
        )
    return spec


def load_markdown_agents(dirs: Iterable[Path]) -> list[SubagentSpec]:
    seen_by_name: dict[str, SubagentSpec] = {}
    for raw in dirs:
        d = Path(raw)
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.md")):
            spec = _parse_one(path)
            if spec is None:
                continue
            seen_by_name[spec["name"]] = spec  # 后到的覆盖先到的
    return list(seen_by_name.values())
