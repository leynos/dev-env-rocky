"""Regression tests for Cursor CLI role wiring."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CURSOR_TASKS = REPO_ROOT / "ansible/roles/cursor_cli/tasks/main.yml"
SITE_PLAYBOOK = REPO_ROOT / "ansible/site.yml"


def test_cursor_cli_role_installs_official_agent_binary() -> None:
    content = CURSOR_TASKS.read_text()

    assert (
        "curl https://cursor.com/install --retry 3 --connect-timeout 10 -fsS | bash"
        in content
    ), "Cursor CLI installation must follow the official Linux/WSL installer"
    assert 'creates: "{{ ansible_env.HOME }}/.local/bin/cursor-agent"' in content, (
        "Cursor CLI installer must be idempotent around the cursor-agent binary"
    )
    assert "set -o pipefail" in content, (
        "Cursor CLI install pipeline must set pipefail so curl failures propagate"
    )
    assert "executable: /bin/bash" in content, (
        "Cursor CLI install task must use /bin/bash to support pipefail"
    )


def test_cursor_cli_role_has_debug_task_for_install_output() -> None:
    content = CURSOR_TASKS.read_text()

    assert "Debug Cursor CLI install output" in content, (
        "Cursor CLI role must include a debug task for install output"
    )
    assert "cursor_cli_install_result" in content, (
        "Cursor CLI debug task must reference cursor_cli_install_result"
    )


def test_site_runs_cursor_cli_before_agent_tools() -> None:
    content = SITE_PLAYBOOK.read_text()

    assert content.index("    - cursor_cli") < content.index("    - agent_tools"), (
        "Cursor CLI must be installed before agent_tools configures Cursor MCPs and skills"
    )
