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
    """Call module.main() with args and return the exit payload."""
    set_module_args(args)
    with pytest.raises(AnsibleExitJson) as exc:
        module.main()
    return exc.value.args[0]


def assert_equal(actual: Any, expected: Any, context: str) -> None:
    """Assert equality with a diagnostic message."""
    assert actual == expected, f"{context}: expected {expected!r}, got {actual!r}"


def assert_is(actual: Any, expected: Any, context: str) -> None:
    """Assert identity with a diagnostic message."""
    assert actual is expected, f"{context}: expected {expected!r}, got {actual!r}"


class _FakeModule:
    """Minimal Ansible module stub for unit tests that bypass AnsibleModule."""

    def get_bin_path(self, value: str, required: bool = False) -> None:
        """Pretend that no executable can be resolved from PATH."""
        return None

    def fail_json(self, **kwargs: object) -> None:
        """Raise a module failure exception with Ansible-style payload data."""
        kwargs["failed"] = True
        raise AnsibleFailJson(kwargs)


def test_uv_tool_parses_tool_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parse valid entries from uv tool list output while ignoring noise."""
    monkeypatch.setattr(
        uv_tool,
        "run",
        lambda module, cmd: (
            0,
            "ruff v0.14.0\nbad line\nnixie v0.1.0 (from git)\n",
            "",
        ),
    )

    assert_equal(
        uv_tool.read_installed_tools(_FakeModule(), "/usr/bin/uv"),
        {
            "ruff": "0.14.0",
            "nixie": "0.1.0",
        },
        "uv_tool should parse installed tool list",
    )


def test_uv_tool_fails_when_tool_list_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surface command details when uv tool list fails."""
    monkeypatch.setattr(uv_tool, "run", lambda module, cmd: (1, "", "boom"))

    with pytest.raises(AnsibleFailJson) as exc:
        uv_tool.read_installed_tools(_FakeModule(), "/usr/bin/uv")

    assert_equal(
        exc.value.args[0]["cmd"],
        ["/usr/bin/uv", "tool", "list"],
        "uv_tool should report failed tool-list command",
    )
    assert_equal(exc.value.args[0]["stderr"], "boom", "uv_tool should surface stderr")


def test_uv_tool_fails_when_binary_not_found() -> None:
    """Fail the module when the configured uv executable cannot be found."""
    with pytest.raises(AnsibleFailJson) as exc:
        uv_tool.resolve_binary(_FakeModule(), "uv")

    assert "Could not find executable" in exc.value.args[0]["msg"]


def test_uv_tool_check_mode_installs_with_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build the expected install command in check mode without running uv."""
    monkeypatch.setattr(uv_tool, "resolve_binary", lambda module, value: "/usr/bin/uv")
    monkeypatch.setattr(uv_tool, "read_installed_tools", lambda module, uv_bin: {})
    monkeypatch.setattr(
        uv_tool, "run", lambda module, cmd: pytest.fail("check mode must not run uv")
    )

    result = run_module(
        uv_tool,
        {
            "_ansible_check_mode": True,
            "name": "ruff",
            "version": "0.14.0",
            "python": "3.12",
            "with_packages": ["pytest"],
            "with_executables_from": ["ansible-core,ansible-lint"],
            "force": True,
        },
    )

    assert_is(result["changed"], True, "uv_tool should report install change")
    assert_equal(
        result["target"], "ruff==0.14.0", "uv_tool should build versioned target"
    )
    assert_equal(
        result["cmd"],
        [
            "/usr/bin/uv",
            "tool",
            "install",
            "--force",
            "--python",
            "3.12",
            "--with",
            "pytest",
            "--with-executables-from",
            "ansible-core,ansible-lint",
            "ruff==0.14.0",
        ],
        "uv_tool should build install command with options",
    )


def test_uv_tool_fails_when_install_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surface stderr when uv tool install fails."""
    monkeypatch.setattr(uv_tool, "resolve_binary", lambda module, value: "/usr/bin/uv")
    monkeypatch.setattr(uv_tool, "read_installed_tools", lambda module, uv_bin: {})
    monkeypatch.setattr(uv_tool, "run", lambda module, cmd: (1, "", "install error"))
    set_module_args({"state": "present", "name": "ruff"})

    with pytest.raises(AnsibleFailJson) as exc:
        uv_tool.main()

    assert exc.value.args[0]["stderr"] == "install error"


def test_uv_tool_fails_when_uninstall_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surface stderr when uv tool uninstall fails."""
    monkeypatch.setattr(uv_tool, "resolve_binary", lambda module, value: "/usr/bin/uv")
    monkeypatch.setattr(
        uv_tool, "read_installed_tools", lambda module, uv_bin: {"ruff": "0.14.0"}
    )
    monkeypatch.setattr(uv_tool, "run", lambda module, cmd: (1, "", "uninstall error"))
    set_module_args({"state": "absent", "name": "ruff"})

    with pytest.raises(AnsibleFailJson) as exc:
        uv_tool.main()

    assert exc.value.args[0]["stderr"] == "uninstall error"


def test_uv_tool_check_mode_uninstalls_existing_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build the expected uninstall command in check mode without running uv."""
    monkeypatch.setattr(uv_tool, "resolve_binary", lambda module, value: "/usr/bin/uv")
    monkeypatch.setattr(
        uv_tool, "read_installed_tools", lambda module, uv_bin: {"ruff": "0.14.0"}
    )
    monkeypatch.setattr(
        uv_tool, "run", lambda module, cmd: pytest.fail("check mode must not run uv")
    )

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


def test_uv_tool_absent_is_idempotent_when_tool_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report no change when an absent uv tool is already missing."""
    monkeypatch.setattr(uv_tool, "resolve_binary", lambda module, value: "/usr/bin/uv")
    monkeypatch.setattr(uv_tool, "read_installed_tools", lambda module, uv_bin: {})
    monkeypatch.setattr(
        uv_tool,
        "run",
        lambda module, cmd: pytest.fail("missing tool must be idempotent"),
    )

    result = run_module(
        uv_tool,
        {
            "name": "ruff",
            "state": "absent",
        },
    )

    assert_equal(
        result,
        {
            "changed": False,
            "name": "ruff",
            "state": "absent",
        },
        "uv_tool should be idempotent when tool is already absent",
    )


def test_uv_tool_uses_spec_over_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefer an explicit package spec over a versioned name target."""
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
