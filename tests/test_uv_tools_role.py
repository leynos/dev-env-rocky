"""Validate Ansible workflow tools in the uv_tools role.

This module protects the `uv_tools` Ansible role contract that managed hosts
receive the Python command-line tools needed for Ansible development:
`ansible`, `molecule`, and `ansible-lint`. The `extract_uv_tool_loop()` helper
isolates the active YAML body of the "Install Python tools via uv" task so
tests check the role's install loop, not unrelated comments or prose. The
parameterized test then ensures each required tool is present as an uncommented
loop item, including the Podman driver package that makes Molecule's configured
Podman scenarios load on managed hosts and the `ansible-core` executable links
that make `ansible-playbook` available on fresh hosts.
"""

import ast
import re
from pathlib import Path

import pytest  # type: ignore[import-untyped]  # ty: ignore[unresolved-import]

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


def parse_loop_value(raw_value: str) -> str | list[str]:
    """Return a structured value from the role's inline loop item syntax."""
    if raw_value.startswith("["):
        value = ast.literal_eval(raw_value)
        assert isinstance(value, list), f"expected list value, got {value!r}"
        assert all(isinstance(item, str) for item in value), (
            f"expected list[str] value, got {value!r}"
        )
        return value
    return raw_value


def parse_uv_tool_loop_items(uv_tool_loop: str) -> list[dict[str, str | list[str]]]:
    """Return the uv_tools loop items as structured dictionaries."""
    loop_item_pattern = re.compile(r"(?m)^    - \{(?P<body>[^{}]+)\}$")
    loop_items: list[dict[str, str | list[str]]] = []
    for match in loop_item_pattern.finditer(uv_tool_loop):
        item: dict[str, str | list[str]] = {}
        for raw_pair in re.split(r",\s*(?=[A-Za-z_]+:)", match.group("body")):
            key, raw_value = raw_pair.split(": ", maxsplit=1)
            item[key] = parse_loop_value(raw_value)
        loop_items.append(item)
    return loop_items


def find_uv_tool_loop_item(
    loop_items: list[dict[str, str | list[str]]], tool_name: str
) -> dict[str, str | list[str]]:
    """Return the loop item matching a uv-managed tool name."""
    for item in loop_items:
        if item.get("name") == tool_name:
            return item
    pytest.fail(f"uv_tools must install {tool_name!r} for Ansible development")
    raise AssertionError(f"uv_tools must install {tool_name!r}")


@pytest.mark.parametrize(
    ("tool_name", "expected_parameters"),
    [
        (
            "ansible",
            {"with_executables_from": ["ansible-core,ansible-lint"]},
        ),
        (
            "molecule",
            {"with_packages": ["molecule-plugins[podman]"]},
        ),
        ("ansible-lint", {}),
    ],
)
def test_uv_tools_installed(
    tool_name: str, expected_parameters: dict[str, list[str]]
) -> None:
    """Ensure each Ansible workflow CLI is installed by uv_tools."""
    tasks_content = UV_TOOLS_TASKS.read_text(encoding="utf-8")
    uv_tool_loop = extract_uv_tool_loop(tasks_content)
    loop_items = parse_uv_tool_loop_items(uv_tool_loop)
    loop_item = find_uv_tool_loop_item(loop_items, tool_name)

    assert loop_item["name"] == tool_name, (
        f"uv_tools must install {tool_name!r} for Ansible development"
    )
    for key, expected_value in expected_parameters.items():
        assert loop_item.get(key) == expected_value, (
            f"uv_tools must install {tool_name!r} with {key}={expected_value!r}"
        )
