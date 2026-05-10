"""Behaviour tests for DeepSeek-TUI agent configuration modules."""

import json
import os
import subprocess
import sys
from pathlib import Path

import tomllib
from ansible_collections.agentic.agent_configs.plugins.modules import (
    deepseek_tui_hook,
    deepseek_tui_mcp,
    deepseek_tui_skill,
)
from pytest_bdd import given, scenarios, then, when  # ty: ignore[unresolved-import]

from ansible_module_runner import run_module

scenarios("features/deepseek_tui_agent_configs.feature")


@given("an empty DeepSeek-TUI home directory", target_fixture="deepseek_home")
def empty_deepseek_home(tmp_path: Path) -> Path:
    """Create an isolated directory used as a fake DeepSeek-TUI home."""
    deepseek_home = tmp_path / ".deepseek"
    deepseek_home.mkdir()
    return deepseek_home


@when("the DeepSeek-TUI modules provision a repository toolset")
def provision_repository_toolset(deepseek_home: Path) -> None:
    """Provision MCP, hook, and skill resources with the new modules."""
    run_module(
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
    run_module(
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
    run_module(
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


def test_deepseek_tui_modules_run_through_ansible_playbook(tmp_path: Path) -> None:
    """Exercise DeepSeek-TUI modules through an actual Ansible playbook boundary."""
    deepseek_home = tmp_path / ".deepseek"
    playbook = tmp_path / "deepseek-tui.yml"
    playbook.write_text(
        f"""---
- name: Configure DeepSeek-TUI through collection modules
  hosts: localhost
  gather_facts: false
  tasks:
    - name: Configure DeepSeek-TUI MCP server
      agentic.agent_configs.deepseek_tui_mcp:
        path: "{deepseek_home / "mcp.json"}"
        name: repo-tools
        transport: stdio
        command: repo-tools-mcp
        args:
          - --stdio

    - name: Configure DeepSeek-TUI hook
      agentic.agent_configs.deepseek_tui_hook:
        path: "{deepseek_home / "config.toml"}"
        event: shell_env
        name: repo-env
        command: repo-env export
        enabled: true

    - name: Configure DeepSeek-TUI skill
      agentic.agent_configs.deepseek_tui_skill:
        path: "{deepseek_home / "skills" / "repo-reviewer"}"
        name: Repo reviewer
        description: Review repository changes.
        body: Read AGENTS.md before reviewing.
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    env["ANSIBLE_COLLECTIONS_PATH"] = str(repo_root / "ansible/ansible_collections")
    env["ANSIBLE_LIBRARY"] = ":".join(
        [
            str(
                repo_root
                / "ansible/ansible_collections/agentic/agent_configs/plugins/modules"
            ),
            str(
                repo_root
                / "ansible/ansible_collections/packaging/tools/plugins/modules"
            ),
        ]
    )
    env["ANSIBLE_MODULE_UTILS"] = str(
        repo_root
        / "ansible/ansible_collections/agentic/agent_configs/plugins/module_utils"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ansible.cli.playbook",
            "-i",
            "localhost,",
            "-c",
            "local",
            str(playbook),
        ],
        check=False,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert (
        json.loads((deepseek_home / "mcp.json").read_text())["servers"]["repo-tools"][
            "command"
        ]
        == "repo-tools-mcp"
    )
    assert "repo-env" in (deepseek_home / "config.toml").read_text()
    assert (deepseek_home / "skills" / "repo-reviewer" / "SKILL.md").exists()
