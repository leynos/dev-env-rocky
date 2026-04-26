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
