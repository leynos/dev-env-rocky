"""Regression tests for agent tool role task definitions."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_TOOLS_TASKS = REPO_ROOT / "ansible/roles/agent_tools/tasks/main.yml"


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

    assert "Configure Codex CLI Firecrawl MCP server" in content, (
        "agent_tools must configure the Codex Firecrawl MCP server"
    )
    assert "command: firecrawl-mcp" in content, (
        "agent_tools must use the firecrawl-mcp executable requested by Codex"
    )
    assert 'FIRECRAWL_API_KEY: "{{ firecrawl_api_key }}"' in content, (
        "agent_tools must source the Firecrawl API key from Ansible Vault"
    )
    assert "no_log: true" in content, (
        "agent_tools must suppress task output because the MCP env contains a secret"
    )
