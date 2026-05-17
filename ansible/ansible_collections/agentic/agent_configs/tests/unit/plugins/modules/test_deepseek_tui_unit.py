"""Unit tests for the deepseek_tui_mcp, deepseek_tui_hook, and deepseek_tui_skill modules."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import pytest
import tomllib
from ansible_collections.agentic.agent_configs.plugins.modules import (
    deepseek_tui_hook,
    deepseek_tui_mcp,
    deepseek_tui_skill,
)
from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    AnsibleFailJson,
    assert_module_fails,
    run_module,
    set_module_args,
)


def _run_module(module, args: dict) -> dict:
    return run_module(module, args)


def _assert_fails(module, args: dict, message: str) -> None:
    return assert_module_fails(module, args, message)


def test_deepseek_tui_hook_writes_toml_and_removes_entry(tmp_path: Path) -> None:
    """Verify DeepSeek-TUI hooks are managed as TOML array-of-table entries."""
    path = tmp_path / "config.toml"
    args = {
        "path": str(path),
        "event": "shell_env",
        "name": "aws-creds",
        "command": "aws-vault export dev --format=env",
        "condition": {"type": "tool_category", "category": "shell"},
        "timeout_secs": 15,
        "enabled": True,
        "default_timeout_secs": 30,
    }

    result = _run_module(deepseek_tui_hook, args)

    assert result["changed"] is True
    assert result["hook"] == {
        "event": "shell_env",
        "command": "aws-vault export dev --format=env",
        "name": "aws-creds",
        "condition": {"type": "tool_category", "category": "shell"},
        "timeout_secs": 15,
    }
    rendered = path.read_text()
    parsed = tomllib.loads(rendered)
    assert parsed == {
        "hooks": {
            "enabled": True,
            "default_timeout_secs": 30,
            "hooks": [
                {
                    "event": "shell_env",
                    "command": "aws-vault export dev --format=env",
                    "name": "aws-creds",
                    "condition": {"type": "tool_category", "category": "shell"},
                    "timeout_secs": 15,
                }
            ],
        }
    }
    assert "[[hooks.hooks]]" in rendered

    rerun_result = _run_module(deepseek_tui_hook, args)
    assert rerun_result["changed"] is False

    absent = _run_module(
        deepseek_tui_hook,
        {
            "path": str(path),
            "event": "shell_env",
            "name": "aws-creds",
            "command": "aws-vault export dev --format=env",
            "state": "absent",
        },
    )
    assert absent["changed"] is True
    assert tomllib.loads(path.read_text()) == {
        "hooks": {"enabled": True, "default_timeout_secs": 30}
    }


def test_deepseek_tui_hook_absent_noop_does_not_return_synthetic_hooks(
    tmp_path: Path,
) -> None:
    """Verify absent no-op results reflect the unchanged on-disk TOML state."""
    path = tmp_path / "config.toml"

    result = _run_module(
        deepseek_tui_hook,
        {
            "path": str(path),
            "event": "shell_env",
            "name": "aws-creds",
            "command": "aws-vault export dev --format=env",
            "state": "absent",
        },
    )

    assert result["changed"] is False
    assert result["hooks"] == {}
    assert not path.exists(), f"expected absent no-op not to create {path}"


def test_deepseek_tui_mcp_rejects_malformed_servers_root(tmp_path: Path) -> None:
    """Verify DeepSeek-TUI MCP rejects non-object servers data."""
    path = tmp_path / "mcp.json"
    path.write_text('{"servers": []}\n')

    _assert_fails(
        deepseek_tui_mcp,
        {
            "path": str(path),
            "name": "repo-tools",
            "transport": "stdio",
            "command": "repo-tools-mcp",
        },
        "Expected 'servers' to be a JSON object",
    )


@pytest.mark.parametrize(
    ("file_content", "read_error"),
    [
        ("{not json}\n", None),
        (None, OSError("permission denied")),
    ],
)
def test_deepseek_tui_mcp_reports_existing_data_read_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    file_content: str | None,
    read_error: OSError | None,
) -> None:
    """Verify DeepSeek-TUI MCP reports unreadable existing config with context."""
    path = tmp_path / "mcp.json"
    if file_content is not None:
        path.write_text(file_content)
    if read_error is not None:

        def fail_read_json(_path: str, *, default: dict) -> NoReturn:
            del default
            raise read_error

        monkeypatch.setattr(deepseek_tui_mcp, "load_json_file", fail_read_json)

    set_module_args(
        {
            "path": str(path),
            "name": "repo-tools",
            "scope": "project",
            "transport": "stdio",
            "command": "repo-tools-mcp",
        }
    )
    with pytest.raises(AnsibleFailJson) as exc:
        deepseek_tui_mcp.main()

    message = exc.value.args[0]["msg"]
    assert "failed to read existing DeepSeek-TUI MCP data" in message
    assert "name='repo-tools'" in message
    assert "scope='project'" in message
    assert f"path={str(path)!r}" in message


@pytest.mark.parametrize(
    ("module", "config_filename", "base_args", "extra_override", "expected_error"),
    [
        (
            deepseek_tui_mcp,
            "mcp.json",
            {
                "name": "repo-tools",
                "transport": "stdio",
                "command": "repo-tools-mcp",
            },
            {"command": "malicious-mcp"},
            "extra cannot override managed MCP fields: command",
        ),
        (
            deepseek_tui_hook,
            "config.toml",
            {
                "event": "shell_env",
                "name": "repo-env",
                "command": "repo-env export",
            },
            {"event": "session_start"},
            "invalid extra keys for deepseek_tui_hook: event",
        ),
    ],
)
def test_extra_cannot_override_managed_fields(
    tmp_path: Path,
    module,
    config_filename: str,
    base_args: dict,
    extra_override: dict,
    expected_error: str,
) -> None:
    """Verify extra data cannot override managed fields in DeepSeek-TUI modules."""
    _assert_fails(
        module,
        {"path": str(tmp_path / config_filename), **base_args, "extra": extra_override},
        expected_error,
    )


def test_deepseek_tui_hook_rejects_malformed_hook_entries(tmp_path: Path) -> None:
    """Verify DeepSeek-TUI hook rejects malformed hooks.hooks TOML values."""
    path = tmp_path / "config.toml"
    path.write_text('[hooks]\nhooks = "bad"\n')

    _assert_fails(
        deepseek_tui_hook,
        {
            "path": str(path),
            "event": "shell_env",
            "name": "repo-env",
            "command": "repo-env export",
        },
        "Expected 'hooks.hooks' to be a list",
    )


def test_deepseek_tui_skill_resolves_workspace_preferred_path_and_scopes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify DeepSeek-TUI skill path resolution and removal semantics."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    project_result = _run_module(
        deepseek_tui_skill,
        {
            "name": "Repository reviewer",
            "scope": "project",
            "project_dir": str(project_dir),
            "description": "Review this repository.",
            "body": "Read AGENTS.md first.",
        },
    )

    expected_dir = project_dir / ".agents" / "skills" / "repository-reviewer"
    assert project_result["directory"] == str(expected_dir)
    assert (
        (expected_dir / "SKILL.md")
        .read_text()
        .startswith(
            '---\nname: "Repository reviewer"\ndescription: "Review this repository."'
        )
    )

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    user_result = _run_module(
        deepseek_tui_skill,
        {
            "name": "User reviewer",
            "scope": "user",
            "description": "Review user-scoped changes.",
        },
    )

    expected_user_dir = home / ".deepseek" / "skills" / "user-reviewer"
    assert user_result["directory"] == str(expected_user_dir)
    assert expected_user_dir.is_dir()
    assert (expected_user_dir / "SKILL.md").is_file()

    explicit_dir = tmp_path / "explicit-skill-dir"

    explicit_result = _run_module(
        deepseek_tui_skill,
        {
            "name": "Explicit reviewer",
            "path": str(explicit_dir),
            "scope": "project",
            "project_dir": str(project_dir),
            "description": "Review explicitly scoped changes.",
            "extra_files": {"references/checklist.md": "Check support files.\n"},
        },
    )

    assert explicit_result["directory"] == str(explicit_dir)
    assert explicit_dir.is_dir()
    assert (explicit_dir / "SKILL.md").is_file()
    assert (explicit_dir / "references" / "checklist.md").is_file()

    absent_result = _run_module(
        deepseek_tui_skill,
        {
            "name": "Explicit reviewer",
            "path": str(explicit_dir),
            "state": "absent",
        },
    )

    assert absent_result["changed"] is True
    assert absent_result["state_transition"] == "removed"
    assert not explicit_dir.exists()


def test_deepseek_tui_skill_metadata_cannot_override_managed_frontmatter(
    tmp_path: Path,
) -> None:
    """Verify DeepSeek-TUI skill metadata cannot override managed front matter."""
    path = tmp_path / "skills" / "repo-reviewer"

    result = _run_module(
        deepseek_tui_skill,
        {
            "path": str(path),
            "name": "Repo reviewer",
            "description": "Review repository changes.",
            "metadata": {
                "name": "Injected name",
                "description": "Injected description.",
                "owner": "release",
            },
        },
    )

    assert result["changed"] is True
    rendered = (path / "SKILL.md").read_text()
    assert 'name: "Repo reviewer"' in rendered
    assert 'description: "Review repository changes."' in rendered
    assert 'owner: "release"' in rendered
    assert "Injected name" not in rendered
    assert "Injected description." not in rendered
