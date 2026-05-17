"""Validate Ansible workflow tools in the uv_tools role.

This module protects the `uv_tools` Ansible role contract that managed hosts
receive the Python command-line tools needed for Ansible development:
`ansible`, `molecule`, and `ansible-lint`. The `extract_uv_tool_loop()` helper
isolates the active YAML body of the "Install Python tools via uv" task so
tests check the role's install loop, not unrelated comments or prose. The
parameterized test then ensures each required tool is present as an uncommented
loop item, including the Podman driver package that makes Molecule's configured
Podman scenarios load on managed hosts.
"""

import re
from pathlib import Path

import pytest  # ty: ignore[unresolved-import]

REPO_ROOT = Path(__file__).resolve().parents[1]
UV_TOOLS_TASKS = REPO_ROOT / "ansible/roles/uv_tools/tasks/main.yml"


def extract_uv_tool_loop(content: str) -> str:
    """Return the body of the uv_tools installation task."""
    match = re.search(
        r"(?ms)^- name: Install Python tools via uv\n(?P<body>.*?)(?=^- name: |\Z)",
        content,
    )
    assert match, "expected the uv_tools role to install Python tools via uv"
    return match.group("body")


@pytest.mark.parametrize(
    ("tool_name", "expected_options"),
    [
        ("ansible", ""),
        ("molecule", ', with_packages: ["molecule-plugins[podman]"]'),
        ("ansible-lint", ""),
    ],
)
def test_ansible_tooling_is_installed_via_uv(
    tool_name: str, expected_options: str
) -> None:
    """Ensure each Ansible workflow CLI is installed by uv_tools."""
    tasks_content = UV_TOOLS_TASKS.read_text(encoding="utf-8")
    uv_tool_loop = extract_uv_tool_loop(tasks_content)
    loop_item_pattern = re.compile(
        rf"(?m)^    - \{{ name: {re.escape(tool_name)}{re.escape(expected_options)} \}}$"
    )

    assert loop_item_pattern.search(uv_tool_loop), (
        f"uv_tools must install {tool_name!r} as an active loop item"
    )
