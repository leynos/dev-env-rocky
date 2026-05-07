"""Regression tests for agent tool role task definitions."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_TOOLS_TASKS = REPO_ROOT / "ansible/roles/agent_tools/tasks/main.yml"


def extract_task(content: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^- name: {re.escape(name)}\n(?P<body>.*?)(?=^- name: |\Z)", content
    )
    assert match, f"expected task named {name!r} to exist"
    return match.group("body")


def test_skill_directory_copies_use_trailing_slash() -> None:
    content = AGENT_TOOLS_TASKS.read_text()

    assert 'src: "{{ item.path }}"' not in content, (
        "agent_tools skill copy tasks must use a trailing slash so Ansible "
        "copies skill directory contents instead of nesting the directory"
    )
    assert content.count('src: "{{ item.path }}/"') == 20, (
        "expected every agent_tools skill copy task to copy directory contents"
    )


def test_helper_executable_directory_exists_before_copy_task() -> None:
    content = AGENT_TOOLS_TASKS.read_text()
    directory_task = extract_task(
        content, "Ensure ~/.local/bin directory exists for helper executables"
    )

    assert content.index(
        "- name: Ensure ~/.local/bin directory exists for helper executables"
    ) < content.index("- name: Install agent-helper-scripts helper executables"), (
        "agent_tools must create ~/.local/bin before copying helper executables"
    )
    assert 'path: "{{ ansible_env.HOME }}/.local/bin"' in directory_task
    assert "state: directory" in directory_task
    assert 'owner: "{{ owner_user }}"' in directory_task
    assert 'group: "{{ owner_user }}"' in directory_task
    assert "mode: '0755'" in directory_task


def test_firecrawl_mcp_uses_vaulted_api_key_without_logging() -> None:
    content = AGENT_TOOLS_TASKS.read_text()
    task = extract_task(content, "Configure Codex CLI Firecrawl MCP server")

    assert "command: firecrawl-mcp" in task, (
        "agent_tools must use the firecrawl-mcp executable requested by Codex"
    )
    assert 'FIRECRAWL_API_KEY: "{{ firecrawl_api_key }}"' in task, (
        "agent_tools must source the Firecrawl API key from Ansible Vault"
    )
    assert "no_log: true" in task, (
        "agent_tools must suppress task output because the MCP env contains a secret"
    )


def test_codex_goals_feature_uses_toml_module() -> None:
    content = AGENT_TOOLS_TASKS.read_text()
    task = extract_task(content, "Enable Codex goals feature")

    assert "agentic.agent_configs.toml_file" in task, (
        "agent_tools must manage Codex config.toml through the toml_file module"
    )
    assert 'path: "{{ ansible_env.HOME }}/.codex/config.toml"' in task
    assert "key: features.goals" in task
    assert "value: true" in task
    assert "mode: '0644'" in task


def test_cursor_cli_gets_skills_mcps_and_no_stop_hook() -> None:
    content = AGENT_TOOLS_TASKS.read_text()
    task = extract_task(content, "Configure Cursor CLI Firecrawl MCP server")
    skill_task = extract_task(content, "Install agent-helper-scripts skills to Cursor")

    assert "agentic.agent_configs.cursor_cli_mcp" in content, (
        "agent_tools must configure Cursor MCPs through the Cursor-specific module"
    )
    assert (
        'dest: "{{ ansible_env.HOME }}/.cursor/skills/{{ item.path | basename }}"'
        in content
    ), "agent_tools must install reusable skills into Cursor's skill directory"
    assert 'FIRECRAWL_API_KEY: "{{ firecrawl_api_key }}"' in task, (
        "Cursor Firecrawl MCP must use the vaulted API key"
    )
    assert "no_log: true" in task, (
        "Cursor Firecrawl MCP must suppress secret-bearing task output"
    )
    assert "cursor_skills_directory.stat.isdir" in skill_task, (
        "Cursor skill copy tasks must skip safely in check mode when the new "
        "directory is only predicted, not created"
    )
    assert "cursor_cli_hook" not in content.lower(), (
        "Cursor CLI does not currently support stop hooks, so agent_tools must not install them"
    )


def test_droid_gets_deepseek_custom_models_without_logging_token() -> None:
    content = AGENT_TOOLS_TASKS.read_text()
    task = extract_task(content, "Configure Factory Droid DeepSeek custom models")

    assert "agentic.agent_configs.factory_droid_model" in task, (
        "agent_tools must configure Droid custom models through the Factory Droid model module"
    )
    assert "https://api.deepseek.com/anthropic" in task, (
        "DeepSeek custom models must use the Anthropic-compatible endpoint"
    )
    assert "deepseek-v4-pro[1m]" in task
    assert "deepseek-v4-pro" in task
    assert 'api_key: "{{ deepseek_api_key }}"' in task, (
        "DeepSeek custom models must use the vaulted API key"
    )
    assert "no_log: true" in task, (
        "DeepSeek custom model task must suppress token-bearing output"
    )
