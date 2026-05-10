"""Regression tests for DeepSeek-TUI owner-user deployment wiring."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_PLAYBOOK = REPO_ROOT / "ansible/site.yml"
ROLE_TASKS = (
    REPO_ROOT
    / "ansible/ansible_collections/agentic/agent_configs/roles/deepseek_tui/tasks/main.yml"
)


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


def test_deepseek_tui_system_packages_install_as_root() -> None:
    content = ROLE_TASKS.read_text()
    task_name = (
        "- name: Ensure DeepSeek-TUI module Python package installer is available"
    )
    package_task = content[content.index(task_name) :]
    next_task = package_task.index(
        "- name: Ensure DeepSeek-TUI module Python dependencies are installed"
    )
    package_task = package_task[:next_task]

    assert "ansible_user_id != 'root'" in package_task, (
        "the system package task must escape non-root owner-user play contexts"
    )
    assert "  become_user: root" in package_task, (
        "RPM installation must run as root when reached from ansible/site.yml"
    )
