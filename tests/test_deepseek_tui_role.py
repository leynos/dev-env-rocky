"""Regression tests for DeepSeek-TUI owner-user deployment wiring."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_PLAYBOOK = REPO_ROOT / "ansible/site.yml"


def test_site_runs_deepseek_tui_after_bun_is_available() -> None:
    content = SITE_PLAYBOOK.read_text()

    assert "    - agentic.agent_configs.deepseek_tui" in content, (
        "the owner-user play must include the reusable DeepSeek-TUI role"
    )
    assert content.index("    - node_packages") < content.index(
        "    - agentic.agent_configs.deepseek_tui"
    ), "DeepSeek-TUI must run after node_packages installs Bun"
    assert content.index("    - agentic.agent_configs.deepseek_tui") < content.index(
        "    - agent_tools"
    ), "DeepSeek-TUI should be deployed before the broader agent tools policy"
