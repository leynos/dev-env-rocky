"""Test agentic uv tool module behaviour.

This module validates ``uv_tool`` parsing, idempotence, and check-mode command
construction through an in-process Ansible harness. Run it with:

    PYTHONPATH=ansible pytest \
        ansible/ansible_collections/agentic/agent_configs/tests/unit/plugins/modules/test_uv_tool.py
"""

from __future__ import annotations

from typing import Any

import pytest

from ansible_collections.agentic.agent_configs.plugins.modules import uv_tool
from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    AnsibleExitJson,
    AnsibleFailJson,
    set_module_args,
)


def run_module(module: Any, args: dict[str, object]) -> dict[str, Any]:
    set_module_args(args)
    with pytest.raises(AnsibleExitJson) as exc:
        module.main()
    return exc.value.args[0]


def assert_equal(actual: Any, expected: Any, context: str) -> None:
    assert actual == expected, f"{context}: expected {expected!r}, got {actual!r}"


def assert_is(actual: Any, expected: Any, context: str) -> None:
    assert actual is expected, f"{context}: expected {expected!r}, got {actual!r}"


def test_uv_tool_parses_tool_list(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeModule:
        def fail_json(self, **kwargs: Any) -> None:
            kwargs["failed"] = True
            raise AnsibleFailJson(kwargs)

    monkeypatch.setattr(
        uv_tool,
        "run",
        lambda module, cmd: (0, "ruff v0.14.0\nbad line\nnixie v0.1.0 (from git)\n", ""),
    )

    assert_equal(uv_tool.read_installed_tools(FakeModule(), "/usr/bin/uv"), {
        "ruff": "0.14.0",
        "nixie": "0.1.0",
    }, "uv_tool should parse installed tool list")


def test_uv_tool_check_mode_installs_with_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uv_tool, "resolve_binary", lambda module, value: "/usr/bin/uv")
    monkeypatch.setattr(uv_tool, "read_installed_tools", lambda module, uv_bin: {})
    monkeypatch.setattr(uv_tool, "run", lambda module, cmd: pytest.fail("check mode must not run uv"))

    result = run_module(
        uv_tool,
        {
            "_ansible_check_mode": True,
            "name": "ruff",
            "version": "0.14.0",
            "python": "3.12",
            "with_packages": ["pytest"],
            "force": True,
        },
    )

    assert_is(result["changed"], True, "uv_tool should report install change")
    assert_equal(result["target"], "ruff==0.14.0", "uv_tool should build versioned target")
    assert_equal(result["cmd"], [
        "/usr/bin/uv",
        "tool",
        "install",
        "--force",
        "--python",
        "3.12",
        "--with",
        "pytest",
        "ruff==0.14.0",
    ], "uv_tool should build install command with options")


def test_uv_tool_check_mode_uninstalls_existing_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uv_tool, "resolve_binary", lambda module, value: "/usr/bin/uv")
    monkeypatch.setattr(uv_tool, "read_installed_tools", lambda module, uv_bin: {"ruff": "0.14.0"})
    monkeypatch.setattr(uv_tool, "run", lambda module, cmd: pytest.fail("check mode must not run uv"))

    result = run_module(
        uv_tool,
        {
            "_ansible_check_mode": True,
            "name": "ruff",
            "state": "absent",
        },
    )

    assert_is(result["changed"], True, "uv_tool should report uninstall change")
    assert_equal(
        result["cmd"],
        ["/usr/bin/uv", "tool", "uninstall", "ruff"],
        "uv_tool should build uninstall command",
    )


def test_uv_tool_absent_is_idempotent_when_tool_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uv_tool, "resolve_binary", lambda module, value: "/usr/bin/uv")
    monkeypatch.setattr(uv_tool, "read_installed_tools", lambda module, uv_bin: {})
    monkeypatch.setattr(uv_tool, "run", lambda module, cmd: pytest.fail("missing tool must be idempotent"))

    result = run_module(
        uv_tool,
        {
            "name": "ruff",
            "state": "absent",
        },
    )

    assert_equal(result, {
        "changed": False,
        "name": "ruff",
        "state": "absent",
    }, "uv_tool should be idempotent when tool is already absent")


def test_uv_tool_uses_spec_over_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uv_tool, "resolve_binary", lambda module, value: "/usr/bin/uv")
    monkeypatch.setattr(uv_tool, "read_installed_tools", lambda module, uv_bin: {})
    monkeypatch.setattr(
        uv_tool,
        "run",
        lambda module, cmd: pytest.fail("check mode must not run uv"),
    )

    result = run_module(
        uv_tool,
        {
            "_ansible_check_mode": True,
            "name": "nixie",
            "version": "1.2.3",
            "spec": "git+https://example.test/nixie",
        },
    )

    assert_equal(
        result["target"],
        "git+https://example.test/nixie",
        "uv_tool should prefer spec over version in target",
    )
    assert_equal(
        result["cmd"][-1],
        "git+https://example.test/nixie",
        "uv_tool should use spec as final install argument",
    )
