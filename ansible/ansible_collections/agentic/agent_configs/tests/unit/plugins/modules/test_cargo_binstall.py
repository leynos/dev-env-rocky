"""Test agentic cargo-binstall module behaviour.

This module validates installed-version parsing and check-mode command
construction for the ``cargo_binstall`` Ansible module. Run it with:

    PYTHONPATH=ansible pytest \
        ansible/ansible_collections/agentic/agent_configs/tests/unit/plugins/modules/test_cargo_binstall.py
"""

from __future__ import annotations

from typing import Any

import pytest

from ansible_collections.agentic.agent_configs.plugins.modules import cargo_binstall
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


def test_cargo_binstall_parses_installed_version(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(module: Any, cmd: list[str], env: dict[str, str] | None = None) -> tuple[int, str, str]:
        return 0, "cargo-nextest v0.9.100:\n    nextest\nother v1.0.0:\n", ""

    monkeypatch.setattr(cargo_binstall, "run", fake_run)

    assert_equal(
        cargo_binstall.read_installed_version(object(), "/usr/bin/cargo", "cargo-nextest", {}),
        "0.9.100",
        "cargo_binstall should parse installed version",
    )
    assert_is(
        cargo_binstall.read_installed_version(object(), "/usr/bin/cargo", "missing", {}),
        None,
        "cargo_binstall should return None for missing package",
    )


def test_cargo_binstall_fails_when_install_list_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeModule:
        def fail_json(self, **kwargs: Any) -> None:
            kwargs["failed"] = True
            raise AnsibleFailJson(kwargs)

    monkeypatch.setattr(cargo_binstall, "run", lambda module, cmd, env=None: (1, "", "boom"))

    with pytest.raises(AnsibleFailJson) as exc:
        cargo_binstall.read_installed_version(FakeModule(), "/usr/bin/cargo", "tool", {})

    assert_equal(
        exc.value.args[0]["cmd"],
        ["/usr/bin/cargo", "install", "--list"],
        "cargo_binstall should report failed install-list command",
    )
    assert_equal(exc.value.args[0]["stderr"], "boom", "cargo_binstall should surface stderr")


def test_cargo_binstall_check_mode_installs_requested_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cargo_binstall, "resolve_binary", lambda module, value: "/usr/bin/cargo")
    monkeypatch.setattr(cargo_binstall, "read_installed_version", lambda module, cargo, name, env: None)
    monkeypatch.setattr(
        cargo_binstall,
        "run",
        lambda module, cmd, env=None: pytest.fail("check mode must not run cargo"),
    )

    result = run_module(
        cargo_binstall,
        {
            "_ansible_check_mode": True,
            "name": "cargo-nextest",
            "version": "0.9.100",
            "root": "/opt/cargo-tools",
            "force": True,
        },
    )

    assert_is(result["changed"], True, "cargo_binstall should report install change")
    assert_equal(result["target"], "cargo-nextest@0.9.100", "cargo_binstall should build target")
    assert_equal(result["cmd"], [
        "/usr/bin/cargo",
        "binstall",
        "--no-confirm",
        "--force",
        "cargo-nextest@0.9.100",
    ], "cargo_binstall should build install command")


def test_cargo_binstall_check_mode_uninstalls_existing_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cargo_binstall, "resolve_binary", lambda module, value: "/usr/bin/cargo")
    monkeypatch.setattr(cargo_binstall, "read_installed_version", lambda module, cargo, name, env: "1.0.0")
    monkeypatch.setattr(
        cargo_binstall,
        "run",
        lambda module, cmd, env=None: pytest.fail("check mode must not run cargo"),
    )

    result = run_module(
        cargo_binstall,
        {
            "_ansible_check_mode": True,
            "name": "cargo-nextest",
            "state": "absent",
            "root": "/opt/cargo-tools",
        },
    )

    assert_is(result["changed"], True, "cargo_binstall should report uninstall change")
    assert_equal(result["cmd"], [
        "/usr/bin/cargo",
        "uninstall",
        "--package",
        "cargo-nextest",
        "--root",
        "/opt/cargo-tools",
    ], "cargo_binstall should build uninstall command")
