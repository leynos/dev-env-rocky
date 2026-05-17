"""Regression tests for uv-managed Python tool task definitions."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
UV_TOOLS_TASKS = REPO_ROOT / "ansible/roles/uv_tools/tasks/main.yml"


def extract_uv_tool_loop(content: str) -> str:
    match = re.search(
        r"(?ms)^- name: Install Python tools via uv\n(?P<body>.*?)(?=^- name: |\Z)",
        content,
    )
    assert match, "expected the uv_tools role to install Python tools via uv"
    return match.group("body")


def test_ansible_tooling_is_installed_via_uv() -> None:
    """Ensure Ansible workflows have their Python CLIs available."""
    tasks_content = UV_TOOLS_TASKS.read_text(encoding="utf-8")
    uv_tool_loop = extract_uv_tool_loop(tasks_content)

    for tool_name in ("ansible", "molecule", "ansible-lint"):
        assert f"name: {tool_name}" in uv_tool_loop, (
            f"uv_tools must install {tool_name!r} for Ansible development"
        )
