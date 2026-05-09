"""Behaviour tests for DeepSeek-TUI agent configuration modules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest  # ty: ignore[unresolved-import]
import tomllib
from ansible_collections.agentic.agent_configs.plugins.modules import (
    deepseek_tui_hook,
    deepseek_tui_mcp,
    deepseek_tui_skill,
)
from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    AnsibleExitJson,
    set_module_args,
)
from pytest_bdd import given, scenarios, then, when  # ty: ignore[unresolved-import]

scenarios("features/deepseek_tui_agent_configs.feature")


def _run_module(module: Any, args: dict[str, Any]) -> dict[str, Any]:
    """Run an Ansible module in-process and return its exit payload."""
    set_module_args(args)
    with pytest.raises(AnsibleExitJson) as exc:
        module.main()
    return exc.value.args[0]


@given("an empty DeepSeek-TUI home directory", target_fixture="deepseek_home")
def empty_deepseek_home(tmp_path: Path) -> Path:
    """Create an isolated directory used as a fake DeepSeek-TUI home."""
    deepseek_home = tmp_path / ".deepseek"
    deepseek_home.mkdir()
    return deepseek_home


@when("the DeepSeek-TUI modules provision a repository toolset")
def provision_repository_toolset(deepseek_home: Path) -> None:
    """Provision MCP, hook, and skill resources with the new modules."""
    _run_module(
        deepseek_tui_mcp,
        {
            "path": str(deepseek_home / "mcp.json"),
            "name": "repo-tools",
            "transport": "stdio",
            "command": "repo-tools-mcp",
            "args": ["--stdio"],
            "env": {"LOG_LEVEL": "info"},
            "required": True,
        },
    )
    _run_module(
        deepseek_tui_hook,
        {
            "path": str(deepseek_home / "config.toml"),
            "event": "shell_env",
            "name": "repo-env",
            "command": "repo-env export",
            "condition": {"type": "tool_category", "category": "shell"},
            "enabled": True,
        },
    )
    _run_module(
        deepseek_tui_skill,
        {
            "path": str(deepseek_home / "skills" / "repo-reviewer"),
            "name": "Repo reviewer",
            "description": "Review repository changes.",
            "body": "Read AGENTS.md before reviewing.",
            "extra_files": {"references/checklist.md": "Check tests and docs.\n"},
        },
    )


@then("the MCP server is written to the DeepSeek servers file")
def mcp_server_is_written(deepseek_home: Path) -> None:
    """Assert the native DeepSeek-TUI MCP JSON shape is rendered."""
    rendered = json.loads((deepseek_home / "mcp.json").read_text())
    assert rendered == {
        "servers": {
            "repo-tools": {
                "args": ["--stdio"],
                "command": "repo-tools-mcp",
                "env": {"LOG_LEVEL": "info"},
                "required": True,
            }
        }
    }


@then("the shell environment hook is written to config TOML")
def shell_environment_hook_is_written(deepseek_home: Path) -> None:
    """Assert the DeepSeek-TUI hook appears under [[hooks.hooks]]."""
    rendered = tomllib.loads((deepseek_home / "config.toml").read_text())
    assert rendered == {
        "hooks": {
            "enabled": True,
            "hooks": [
                {
                    "event": "shell_env",
                    "command": "repo-env export",
                    "name": "repo-env",
                    "condition": {"type": "tool_category", "category": "shell"},
                }
            ],
        }
    }


@then("the skill bundle is written to the DeepSeek skills directory")
def skill_bundle_is_written(deepseek_home: Path) -> None:
    """Assert the DeepSeek-TUI skill directory contains primary and support files."""
    skill_dir = deepseek_home / "skills" / "repo-reviewer"
    assert (skill_dir / "SKILL.md").read_text() == (
        '---\nname: "Repo reviewer"\n'
        'description: "Review repository changes."\n---\n\n'
        "Read AGENTS.md before reviewing.\n"
    )
    assert (skill_dir / "references" / "checklist.md").read_text() == (
        "Check tests and docs.\n"
    )
