"""Regression tests for the sccache user role task definitions."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCCACHE_USER_TASKS = REPO_ROOT / "ansible/roles/sccache_user/tasks/main.yml"


def test_sccache_user_role_uses_structured_config_modules() -> None:
    content = SCCACHE_USER_TASKS.read_text()

    assert "ansible.builtin.blockinfile" not in content, (
        "sccache_user must manage Codex and Claude settings with structured "
        "file modules instead of fragile text blocks"
    )
    assert "agentic.agent_configs.toml_file" in content, (
        "sccache_user must manage Codex config.toml through the toml_file module"
    )
    assert "agentic.agent_configs.json_file" in content, (
        "sccache_user must manage Claude settings.json through the json_file module"
    )
    assert "{{ ansible_env.HOME }}/.codex/config.toml" in content, (
        "sccache_user must write Codex environment settings to config.toml"
    )
    assert "{{ ansible_env.HOME }}/.claude/settings.json" in content, (
        "sccache_user must write Claude environment settings to settings.json"
    )


def test_sccache_user_role_removes_obsolete_claude_toml_config() -> None:
    content = SCCACHE_USER_TASKS.read_text()

    assert "{{ ansible_env.HOME }}/.claude/config.toml" in content, (
        "sccache_user must clean up the obsolete invalid Claude TOML config"
    )
    assert "state: absent" in content, (
        "sccache_user must remove the obsolete Claude config.toml"
    )
