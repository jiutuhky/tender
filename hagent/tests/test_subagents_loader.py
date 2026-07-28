import logging
from pathlib import Path

import yaml

from hagent.subagents.loader import load_markdown_agents


def _write(path: Path, frontmatter: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")


def test_load_basic_agent(tmp_path):
    _write(tmp_path / "reviewer.md", {"name": "reviewer", "description": "审查代码"}, "你是 reviewer。")
    specs = load_markdown_agents([tmp_path])
    assert len(specs) == 1
    assert specs[0]["name"] == "reviewer"
    assert specs[0]["description"] == "审查代码"
    assert specs[0]["system_prompt"].strip() == "你是 reviewer。"
    assert specs[0]["source"] == str(tmp_path)


def test_load_with_tools_and_disallowed_and_model(tmp_path):
    _write(
        tmp_path / "researcher.md",
        {
            "name": "researcher",
            "description": "调研代理",
            "tools": ["Read", "Bash"],
            "disallowedTools": ["Bash"],
            "model": "haiku",
            "color": "blue",
        },
        "调研代理 system prompt。",
    )
    specs = load_markdown_agents([tmp_path])
    assert specs[0]["tools"] == ["Read", "Bash"]
    assert specs[0]["disallowed_tools"] == ["Bash"]
    assert specs[0]["model"] == "haiku"
    assert specs[0]["color"] == "blue"


def test_missing_name_or_description_is_skipped(tmp_path):
    _write(tmp_path / "no_name.md", {"description": "x"}, "body")
    _write(tmp_path / "no_desc.md", {"name": "x"}, "body")
    assert load_markdown_agents([tmp_path]) == []


def test_unsupported_fields_are_logged_and_ignored(tmp_path, caplog):
    _write(
        tmp_path / "fancy.md",
        {
            "name": "fancy",
            "description": "演示",
            "permissionMode": "plan",
            "maxTurns": 7,
            "skills": ["a"],
            "mcpServers": ["x"],
            "memory": "user",
            "isolation": "worktree",
            "background": True,
        },
        "正文",
    )
    with caplog.at_level(logging.WARNING, logger="hagent.subagents.loader"):
        specs = load_markdown_agents([tmp_path])
    assert specs[0]["name"] == "fancy"
    for key in ("permissionMode", "maxTurns", "mcpServers", "memory", "isolation", "background"):
        assert key not in specs[0]
        assert key in caplog.text
    assert specs[0]["skills"] == ["a"]


def test_load_with_skills(tmp_path):
    _write(
        tmp_path / "planner.md",
        {
            "name": "planner",
            "description": "规划代理",
            "skills": ["writing-plans", "review"],
        },
        "规划代理 system prompt。",
    )
    specs = load_markdown_agents([tmp_path])
    assert specs[0]["skills"] == ["writing-plans", "review"]


def test_dir_priority_later_overrides_earlier(tmp_path):
    user = tmp_path / "user"
    project = tmp_path / "project"
    _write(user / "x.md", {"name": "x", "description": "user版"}, "u")
    _write(project / "x.md", {"name": "x", "description": "project版"}, "p")
    specs = load_markdown_agents([user, project])
    by_name = {s["name"]: s for s in specs}
    assert by_name["x"]["description"] == "project版"


def test_missing_directory_is_silently_ignored(tmp_path):
    assert load_markdown_agents([tmp_path / "does_not_exist"]) == []


def test_non_md_files_are_ignored(tmp_path):
    (tmp_path / "README.txt").write_text("not an agent", encoding="utf-8")
    assert load_markdown_agents([tmp_path]) == []


def test_invalid_yaml_is_skipped_with_warning(tmp_path, caplog):
    (tmp_path / "bad.md").write_text("---\nname: [unclosed\n---\nbody", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="hagent.subagents.loader"):
        specs = load_markdown_agents([tmp_path])
    assert specs == []
    assert "bad.md" in caplog.text


def test_load_expanded_plugin_format(tmp_path):
    # CC 插件源文件的真实形态：description 无引号、跨真实多行、内嵌 <example> 伪键，
    # 后面才跟 model/color/tools。严格 YAML 解析不了，靠宽松回退兜底。
    (tmp_path / "parser.md").write_text(
        "---\n"
        "name: business-requirements-parser\n"
        "description: Use this agent to parse business requirements (商务要求). Examples:\n"
        "\n"
        "<example>\n"
        "Context: The skill extracted a file.\n"
        'user: "Parse foo.md into foo.json. Source file: orig.md"\n'
        'assistant: "I will use the parser agent."\n'
        "<commentary>\n"
        "Specializes in structured JSON.\n"
        "</commentary>\n"
        "</example>\n"
        "\n"
        "model: inherit\n"
        "color: magenta\n"
        'tools: ["Read", "Write", "Grep"]\n'
        "---\n"
        "You are a specialized parser agent.\n",
        encoding="utf-8",
    )
    specs = load_markdown_agents([tmp_path])
    assert len(specs) == 1
    s = specs[0]
    assert s["name"] == "business-requirements-parser"
    # description 必须包含整段 examples（伪键行不被当成 frontmatter key）
    assert s["description"].startswith("Use this agent to parse business requirements")
    assert "<example>" in s["description"]
    assert "Context: The skill extracted a file." in s["description"]
    assert "Source file: orig.md" in s["description"]
    assert s["tools"] == ["Read", "Write", "Grep"]
    assert s["model"] == "inherit"
    assert s["color"] == "magenta"
    assert s["system_prompt"].strip() == "You are a specialized parser agent."


def test_tools_as_comma_separated_string(tmp_path):
    # CC formatAgentAsMarkdown 写的是逗号分隔（非数组）：tools: Read, Write, Grep
    (tmp_path / "a.md").write_text(
        "---\n"
        "name: a\n"
        "description: x. Examples:\n"
        "\n"
        "<example>\nContext: y.\n</example>\n"
        "tools: Read, Write, Grep\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    specs = load_markdown_agents([tmp_path])
    assert specs[0]["tools"] == ["Read", "Write", "Grep"]


def test_cc_canonical_single_line_escaped_description_roundtrip(tmp_path):
    # CC 规范磁盘格式：description 单行双引号、换行转义成字面 \\n（盘上两反斜杠+n）。
    # YAML 解出字面 \n（反斜杠+n），loader 再 replace 还原真换行（对齐 loadAgentsDir:565）。
    (tmp_path / "c.md").write_text(
        "---\n"
        "name: c\n"
        'description: "Use this. Examples:\\\\n\\\\n<example>\\\\nContext: did.\\\\n</example>"\n'
        "tools: Read, Write\n"
        "model: inherit\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    specs = load_markdown_agents([tmp_path])
    s = specs[0]
    assert s["name"] == "c"
    assert "\n" in s["description"]  # 字面 \n 被还原为真换行
    assert "<example>" in s["description"]
    assert "Context: did." in s["description"]
    assert s["tools"] == ["Read", "Write"]


def test_unknown_frontmatter_keys_are_logged(tmp_path, caplog):
    _write(
        tmp_path / "typo.md",
        {"name": "typo", "description": "x", "tool": ["Read"], "colour": "blue"},
        "body",
    )
    with caplog.at_level(logging.WARNING, logger="hagent.subagents.loader"):
        specs = load_markdown_agents([tmp_path])
    assert specs[0]["name"] == "typo"
    # tool / colour are typos and not in tools/color → must be warned
    assert "tool" in caplog.text
    assert "colour" in caplog.text
    # tools (recognized) and permissionMode (in IGNORED list) should NOT be in the unknown-keys warning
    # but permissionMode wasn't in the file so it can't appear anyway
    assert "specs[0]" not in caplog.text  # sanity that we didn't accidentally leak the spec dict
