"""Regression tests for agent tool role task definitions."""

from pathlib import Path
import re


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
    assert content.count('src: "{{ item.path }}/"') == 18, (
        "expected every agent_tools skill copy task to copy directory contents"
    )


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
