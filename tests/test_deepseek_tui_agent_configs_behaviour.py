"""Behaviour tests for DeepSeek-TUI agent configuration modules."""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from ansible_collections.agentic.agent_configs.plugins.modules import (
    deepseek_tui_hook,
    deepseek_tui_mcp,
    deepseek_tui_skill,
)
from ansible_module_runner import run_module
from pytest_bdd import (  # type: ignore[unresolved-import]  # ty: ignore[unresolved-import]
    given,
    scenarios,
    then,
    when,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

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
    expected = {
        "servers": {
            "repo-tools": {
                "args": ["--stdio"],
                "command": "repo-tools-mcp",
                "env": {"LOG_LEVEL": "info"},
                "required": True,
            }
        }
    }
    assert rendered == expected, (
        f"Expected mcp.json to contain repo-tools MCP server entry, got: {rendered}"
    )


@then("the shell environment hook is written to config TOML")
def shell_environment_hook_is_written(deepseek_home: Path) -> None:
    """Assert the DeepSeek-TUI hook appears under [[hooks.hooks]]."""
    rendered = tomllib.loads((deepseek_home / "config.toml").read_text())
    expected = {
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
    assert rendered == expected, (
        f"Expected config.toml to contain repo-env hook, got: {rendered}"
    )


@then("the skill bundle is written to the DeepSeek skills directory")
def skill_bundle_is_written(deepseek_home: Path) -> None:
    """Assert the DeepSeek-TUI skill directory contains primary and support files."""
    skill_dir = deepseek_home / "skills" / "repo-reviewer"
    expected_skill = (
        '---\nname: "Repo reviewer"\n'
        'description: "Review repository changes."\n---\n\n'
        "Read AGENTS.md before reviewing.\n"
    )
    assert (skill_dir / "SKILL.md").read_text() == expected_skill, (
        "Expected SKILL.md to contain expected front matter and body"
    )
    assert (
        skill_dir / "references" / "checklist.md"
    ).read_text() == "Check tests and docs.\n", (
        "Expected references/checklist.md to contain expected checklist content"
    )


def test_hook_extra_cannot_override_managed_fields() -> None:
    """Extra hook fields must not replace identity or managed behaviour fields."""
    hook = deepseek_tui_hook.build_hook_definition(
        deepseek_tui_hook.HookParams(
            event="shell_env",
            command="repo-env export",
            name="repo-env",
            timeout_secs=30,
            extra={
                "event": "session_start",
                "command": "rm -rf /",
                "name": "override",
                "timeout_secs": 1,
                "custom_field": "preserved",
            },
        )
    )

    assert hook == {
        "event": "shell_env",
        "command": "repo-env export",
        "name": "repo-env",
        "timeout_secs": 30,
        "custom_field": "preserved",
    }, f"unexpected hook: {hook!r}"


def _write_deepseek_tui_playbook(tmp_path: Path, deepseek_home: Path) -> Path:
    """Write a minimal DeepSeek-TUI provisioning playbook and return its path."""
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
    return playbook


def _build_ansible_env() -> dict[str, str]:
    """Return an environment dict with Ansible collection search paths configured."""
    env = os.environ.copy()
    env["ANSIBLE_COLLECTIONS_PATH"] = str(_REPO_ROOT / "ansible/ansible_collections")
    env["ANSIBLE_LIBRARY"] = os.pathsep.join([
        str(
            _REPO_ROOT
            / "ansible/ansible_collections/agentic/agent_configs/plugins/modules"
        ),
        str(_REPO_ROOT / "ansible/ansible_collections/packaging/tools/plugins/modules"),
    ])
    env["ANSIBLE_MODULE_UTILS"] = str(
        _REPO_ROOT
        / "ansible/ansible_collections/agentic/agent_configs/plugins/module_utils"
    )
    return env


def _run_ansible_playbook(
    playbook: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run *playbook* via the Ansible CLI and return the completed process."""
    try:
        return subprocess.run(
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
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            "Ansible playbook did not complete within 120 seconds"
        ) from exc


def _assert_deepseek_tui_artifacts(
    deepseek_home: Path,
    result: subprocess.CompletedProcess[str],
) -> None:
    """Assert the playbook succeeded and wrote the expected DeepSeek-TUI artefacts."""
    assert result.returncode == 0, result.stderr + result.stdout
    servers = json.loads((deepseek_home / "mcp.json").read_text())["servers"]
    actual_command = servers["repo-tools"]["command"]
    assert actual_command == "repo-tools-mcp", (
        f"Expected repo-tools command to be repo-tools-mcp, got: {actual_command}"
    )
    config_toml = (deepseek_home / "config.toml").read_text()
    assert "repo-env" in config_toml, (
        f"Expected config.toml to contain repo-env hook, got: {config_toml}"
    )
    skill_path = deepseek_home / "skills" / "repo-reviewer" / "SKILL.md"
    assert skill_path.exists(), "Expected SKILL.md to exist under skills/repo-reviewer"


def test_deepseek_tui_modules_run_through_ansible_playbook(tmp_path: Path) -> None:
    """Exercise DeepSeek-TUI modules through an actual Ansible playbook boundary."""
    deepseek_home = tmp_path / ".deepseek"
    playbook = _write_deepseek_tui_playbook(tmp_path, deepseek_home)
    result = _run_ansible_playbook(playbook, _build_ansible_env())
    _assert_deepseek_tui_artifacts(deepseek_home, result)
