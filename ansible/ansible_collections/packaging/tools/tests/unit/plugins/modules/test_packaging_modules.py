"""Test packaging.tools Ansible modules.

This module exercises the Bun, cargo-binstall, and uv module behaviours through
an in-process Ansible harness. The shared conftest.py fixture patches module
exit helpers and resets Ansible arguments between tests.

Example invocation::

    PYTHONPATH=ansible pytest \
        ansible/ansible_collections/packaging/tools/tests/unit/plugins/modules/test_packaging_modules.py
"""

from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
from typing import Any

import pytest

from ansible_collections.agentic.agent_configs.plugins.module_utils import bun_paths
from ansible_collections.packaging.tools.plugins.modules import (
    bun_global,
    cargo_binstall,
    uv_tool,
)

from ansible_collections.packaging.tools.tests.unit.plugins.modules.module_test_utils import (
    AnsibleExitJson,
    AnsibleFailJson,
    set_module_args,
)


def run_module(module: Any, args: dict[str, Any]) -> dict[str, Any]:
    set_module_args(args)
    with pytest.raises(AnsibleExitJson) as exc:
        module.main()
    return exc.value.args[0]


def assert_equal(actual: Any, expected: Any, context: str) -> None:
    assert actual == expected, f"{context}: expected {expected!r}, got {actual!r}"


def assert_is(actual: Any, expected: Any, context: str) -> None:
    assert actual is expected, f"{context}: expected {expected!r}, got {actual!r}"


def test_bun_package_json_path_handles_scoped_packages() -> None:
    assert_equal(
        bun_global.package_json_path("/global", "@scope/tool"),
        "/global/node_modules/@scope/tool/package.json",
        "bun_global.package_json_path should handle scoped package paths",
    )


def test_bun_read_installed_version(tmp_path: Path) -> None:
    package_json = tmp_path / "package.json"

    assert_is(
        bun_global.read_installed_version(str(package_json)),
        None,
        "bun_global.read_installed_version should return None for missing metadata",
    )

    package_json.write_text(json.dumps({"version": "1.2.3"}))

    assert_equal(
        bun_global.read_installed_version(str(package_json)),
        "1.2.3",
        "bun_global.read_installed_version should read package version",
    )


def test_bun_expand_home_uses_home_for_tilde(monkeypatch: pytest.MonkeyPatch) -> None:
    home = "/tmp/test-home"
    monkeypatch.setenv("HOME", home)

    assert_equal(bun_paths.expand_home("~"), home, "bun_paths.expand_home should expand bare tilde")
    assert_equal(
        bun_paths.expand_home("~/projects"),
        str(Path(home) / "projects"),
        "bun_paths.expand_home should expand tilde-prefixed paths",
    )


def test_bun_expand_home_uses_system_home_when_home_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOME", raising=False)
    system_home = Path.home()

    assert_equal(
        bun_paths.expand_home("~"),
        str(system_home),
        "bun_paths.expand_home should use system home when HOME is missing",
    )
    assert_equal(
        bun_paths.expand_home("~/projects"),
        str(system_home / "projects"),
        "bun_paths.expand_home should expand child path without HOME",
    )


def test_bun_expand_home_preserves_expanduser_user_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/tmp/test-home")
    user_path = f"~{getpass.getuser()}/projects"

    assert_equal(
        bun_paths.expand_home(user_path),
        os.path.expanduser(user_path),
        "bun_paths.expand_home should preserve expanduser user lookup",
    )


def test_bun_expand_home_returns_original_unknown_user_path() -> None:
    user_path = "~definitely-no-such-user-xyz/projects"

    assert_equal(
        bun_paths.expand_home(user_path),
        user_path,
        "bun_paths.expand_home should preserve unknown user paths",
    )


def test_bun_resolve_global_dir_env_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    home = "/tmp/test-home"
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("BUN_INSTALL_GLOBAL_DIR", "~/bun-global")

    assert_equal(
        bun_paths.resolve_global_dir(None),
        str(Path(home) / "bun-global"),
        "bun_paths.resolve_global_dir should prefer env over default",
    )


def test_bun_resolve_global_dir_explicit_param_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    home = "/tmp/test-home"
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("BUN_INSTALL_GLOBAL_DIR", "~/ignored-global")

    assert_equal(
        bun_paths.resolve_global_dir("~/explicit-global"),
        str(Path(home) / "explicit-global"),
        "bun_paths.resolve_global_dir should prefer explicit parameter",
    )


def test_bun_resolve_global_bin_dir_env_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    home = "/tmp/test-home"
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("BUN_INSTALL_BIN", "~/bun-bin")

    assert_equal(
        bun_paths.resolve_global_bin_dir(None),
        str(Path(home) / "bun-bin"),
        "bun_paths.resolve_global_bin_dir should prefer env over default",
    )


def test_bun_resolve_global_bin_dir_explicit_param_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    home = "/tmp/test-home"
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("BUN_INSTALL_BIN", "~/ignored-bin")

    assert_equal(
        bun_paths.resolve_global_bin_dir("~/explicit-bin"),
        str(Path(home) / "explicit-bin"),
        "bun_paths.resolve_global_bin_dir should prefer explicit parameter",
    )


def test_bun_global_check_mode_installs_missing_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bun_global, "resolve_binary", lambda module, value: "/usr/bin/bun")
    monkeypatch.setattr(bun_global, "read_installed_version", lambda path: None)
    monkeypatch.setattr(
        bun_global,
        "run",
        lambda module, cmd, env=None: pytest.fail("check mode must not run bun"),
    )

    result = run_module(
        bun_global,
        {
            "_ansible_check_mode": True,
            "name": "@scope/tool",
            "version": "1.2.3",
            "global_dir": str(tmp_path / "global"),
            "global_bin_dir": str(tmp_path / "bin"),
            "ignore_scripts": True,
        },
    )

    assert_is(result["changed"], True, "bun_global should report changed in check mode")
    assert_equal(result["target"], "@scope/tool@1.2.3", "bun_global should build versioned target")
    assert_equal(
        result["cmd"],
        ["/usr/bin/bun", "install", "-g", "--ignore-scripts", "@scope/tool@1.2.3"],
        "bun_global should build install command with ignore scripts",
    )


def test_bun_global_reports_present_package_without_running_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bun_global, "resolve_binary", lambda module, value: "/usr/bin/bun")
    monkeypatch.setattr(bun_global, "read_installed_version", lambda path: "1.2.3")
    monkeypatch.setattr(
        bun_global,
        "run",
        lambda module, cmd, env=None: pytest.fail("installed package must be idempotent"),
    )

    result = run_module(
        bun_global,
        {
            "name": "tool",
            "version": "1.2.3",
            "global_dir": str(tmp_path / "global"),
            "global_bin_dir": str(tmp_path / "bin"),
        },
    )

    assert_equal(result, {
        "changed": False,
        "name": "tool",
        "state": "present",
        "installed_version": "1.2.3",
        "global_dir": str(tmp_path / "global"),
        "global_bin_dir": str(tmp_path / "bin"),
    }, "bun_global should be idempotent for installed package")


def test_cargo_binstall_parses_installed_version(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(module, cmd, env=None):
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
        def fail_json(self, **kwargs):
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


def test_uv_tool_parses_tool_list(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeModule:
        def fail_json(self, **kwargs):
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
            "_ansible_check_mode": True,
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
