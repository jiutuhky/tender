from deepagents import FilesystemPermission

from hagent.permissions import DEFAULT_PERMISSIONS


def test_default_permissions_is_list_of_filesystem_permissions():
    assert isinstance(DEFAULT_PERMISSIONS, list)
    assert len(DEFAULT_PERMISSIONS) >= 2
    for p in DEFAULT_PERMISSIONS:
        assert isinstance(p, FilesystemPermission)


def test_deny_rule_comes_before_allow_rule():
    # first-match-wins：deny 必须排前面
    first_deny_idx = next(i for i, p in enumerate(DEFAULT_PERMISSIONS) if p.mode == "deny")
    first_allow_idx = next(i for i, p in enumerate(DEFAULT_PERMISSIONS) if p.mode == "allow")
    assert first_deny_idx < first_allow_idx


def test_workspace_is_allowed_path():
    allow_rules = [p for p in DEFAULT_PERMISSIONS if p.mode == "allow"]
    paths_allowed = [path for p in allow_rules for path in p.paths]
    assert any("workspace" in path for path in paths_allowed)


def test_system_dirs_are_denied():
    deny_rules = [p for p in DEFAULT_PERMISSIONS if p.mode == "deny"]
    paths_denied = [path for p in deny_rules for path in p.paths]
    for sysdir in ["/etc/**", "/usr/**", "/var/**", "/root/**"]:
        assert sysdir in paths_denied
