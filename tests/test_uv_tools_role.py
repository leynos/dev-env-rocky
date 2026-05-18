"""Validate Ansible workflow tools in the uv_tools role.

This module protects the `uv_tools` Ansible role contract that managed hosts
receive the Python command-line tools needed for Ansible development:
`ansible`, `molecule`, and `ansible-lint`. The `_extract_uv_tool_loop()` helper
isolates the active YAML body of the "Install Python tools via uv" task so
tests check the role's install loop, not unrelated comments or prose. The
parameterized test then ensures each required tool is present as an uncommented
loop item, including the Podman driver package that makes Molecule's configured
Podman scenarios load on managed hosts and the `ansible-core` executable links
that make `ansible-playbook` available on fresh hosts.
"""

import ast
import importlib
import re
from pathlib import Path
from typing import Any

import pytest  # type: ignore[import-untyped]  # ty: ignore[unresolved-import]

try:
    yaml_loader: Any = importlib.import_module("yaml")
except ModuleNotFoundError:
    yaml_loader = None

REPO_ROOT = Path(__file__).resolve().parents[1]
UV_TOOLS_TASKS = REPO_ROOT / "ansible/roles/uv_tools/tasks/main.yml"


def _extract_uv_tool_loop(content: str) -> str:
    """Return the body of the uv_tools installation task."""
    match = re.search(
        r"(?ms)^- name: Install Python tools via uv\n(?P<body>.*?)(?=^- name: |\Z)",
        content,
    )
    assert match, "expected the uv_tools role to install Python tools via uv"
    return match.group("body")


def _parse_uv_tool_loop_items(uv_tool_loop: str) -> list[dict[str, object]]:
    """Return the uv_tools loop items as structured dictionaries."""
    if yaml_loader is None:
        return _parse_inline_loop_items(uv_tool_loop)

    task_body = yaml_loader.safe_load(uv_tool_loop)
    assert isinstance(task_body, dict), "expected uv tool task body to be a mapping"
    loop_items = task_body.get("loop")
    assert isinstance(loop_items, list), "expected uv tool task body to include a loop"
    assert all(isinstance(item, dict) for item in loop_items), (
        f"expected uv tool loop items to be mappings, got {loop_items!r}"
    )
    return loop_items


def _parse_inline_loop_items(uv_tool_loop: str) -> list[dict[str, object]]:
    """Return uv_tools loop items without requiring an external YAML package."""
    loop_item_pattern = re.compile(r"(?m)^    - \{(?P<body>[^{}]+)\}$")
    loop_items: list[dict[str, object]] = []
    for match in loop_item_pattern.finditer(uv_tool_loop):
        item: dict[str, object] = {}
        for raw_pair in re.split(r",\s*(?=[A-Za-z_]+:)", match.group("body")):
            key, raw_value = raw_pair.split(": ", maxsplit=1)
            item[key] = _parse_loop_value(raw_value)
        loop_items.append(item)
    return loop_items


def _parse_loop_value(raw_value: str) -> str | list[str]:
    """Return a structured value from the role's inline loop item syntax."""
    if raw_value.startswith("["):
        value = ast.literal_eval(raw_value)
        assert isinstance(value, list), f"expected list value, got {value!r}"
        assert all(isinstance(item, str) for item in value), (
            f"expected list[str] value, got {value!r}"
        )
        return value
    return raw_value


def _find_uv_tool_loop_item(
    loop_items: list[dict[str, object]], tool_name: str
) -> dict[str, object]:
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
    uv_tool_loop = _extract_uv_tool_loop(tasks_content)
    loop_items = _parse_uv_tool_loop_items(uv_tool_loop)
    loop_item = _find_uv_tool_loop_item(loop_items, tool_name)

    assert loop_item["name"] == tool_name, (
        f"uv_tools must install {tool_name!r} for Ansible development"
    )
    for key, expected_value in expected_parameters.items():
        assert loop_item.get(key) == expected_value, (
            f"uv_tools must install {tool_name!r} with {key}={expected_value!r}"
        )
    for optional_key in ("with_executables_from", "with_packages"):
        if optional_key not in expected_parameters:
            assert optional_key not in loop_item or loop_item[optional_key] in (
                None,
                [],
            ), (
                f"uv_tools must not install {tool_name!r} with unexpected "
                f"{optional_key}={loop_item[optional_key]!r}"
            )
