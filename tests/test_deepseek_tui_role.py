"""Regression tests for DeepSeek-TUI owner-user deployment wiring."""

from pathlib import Path

import yaml  # ty: ignore[unresolved-import]

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_PLAYBOOK = REPO_ROOT / "ansible/site.yml"
ROLE_TASKS = (
    REPO_ROOT
    / "ansible/ansible_collections/agentic/agent_configs/roles/deepseek_tui/tasks/main.yml"
)


def test_site_runs_deepseek_tui_after_bun_is_available() -> None:
    plays = yaml.safe_load(SITE_PLAYBOOK.read_text())
    owner_play = next(
        play
        for play in plays
        if play["name"] == "Configure user environment for owner user"
    )
    roles = owner_play["roles"]

    assert "agentic.agent_configs.deepseek_tui" in roles, (
        "the owner-user play must include the reusable DeepSeek-TUI role"
    )
    assert roles.index("node_packages") < roles.index(
        "agentic.agent_configs.deepseek_tui"
    ), "DeepSeek-TUI must run after node_packages installs Bun"
    assert roles.index("agentic.agent_configs.deepseek_tui") < roles.index(
        "agent_tools"
    ), "DeepSeek-TUI should be deployed before the broader agent tools policy"


def test_deepseek_tui_system_packages_install_as_root() -> None:
    tasks = yaml.safe_load(ROLE_TASKS.read_text())
    package_task = next(
        task
        for task in tasks
        if task["name"]
        == "Ensure DeepSeek-TUI module Python package installer is available"
    )

    assert package_task["when"] == "deepseek_tui_manage_python_dependencies | bool"
    assert package_task["become"] == (
        "{{ ansible_user_id is not defined or ansible_user_id != 'root' }}"
    ), "the system package task must only escalate from non-root contexts"
    assert package_task.get("become_user") == "root", (
        "RPM installation must run as root when reached from ansible/site.yml"
    )
