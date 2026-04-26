from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def run_module(module, args: dict):
    set_module_args(args)
    with pytest.raises(AnsibleExitJson) as exc:
        module.main()
    return exc.value.args[0]


def test_bun_package_json_path_handles_scoped_packages() -> None:
    assert bun_global.package_json_path("/global", "@scope/tool") == ("/global/node_modules/@scope/tool/package.json")


def test_bun_read_installed_version(tmp_path: Path) -> None:
    package_json = tmp_path / "package.json"

    assert bun_global.read_installed_version(str(package_json)) is None

    package_json.write_text(json.dumps({"version": "1.2.3"}))

    assert bun_global.read_installed_version(str(package_json)) == "1.2.3"


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

    assert result["changed"] is True
    assert result["target"] == "@scope/tool@1.2.3"
    assert result["cmd"] == ["/usr/bin/bun", "install", "-g", "--ignore-scripts", "@scope/tool@1.2.3"]


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

    assert result == {
        "changed": False,
        "name": "tool",
        "state": "present",
        "installed_version": "1.2.3",
        "global_dir": str(tmp_path / "global"),
        "global_bin_dir": str(tmp_path / "bin"),
    }


def test_cargo_binstall_parses_installed_version(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(module, cmd, env=None):
        return 0, "cargo-nextest v0.9.100:\n    nextest\nother v1.0.0:\n", ""

    monkeypatch.setattr(cargo_binstall, "run", fake_run)

    assert cargo_binstall.read_installed_version(object(), "/usr/bin/cargo", "cargo-nextest", {}) == "0.9.100"
    assert cargo_binstall.read_installed_version(object(), "/usr/bin/cargo", "missing", {}) is None


def test_cargo_binstall_fails_when_install_list_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeModule:
        def fail_json(self, **kwargs):
            kwargs["failed"] = True
            raise AnsibleFailJson(kwargs)

    monkeypatch.setattr(cargo_binstall, "run", lambda module, cmd, env=None: (1, "", "boom"))

    with pytest.raises(AnsibleFailJson) as exc:
        cargo_binstall.read_installed_version(FakeModule(), "/usr/bin/cargo", "tool", {})

    assert exc.value.args[0]["cmd"] == ["/usr/bin/cargo", "install", "--list"]
    assert exc.value.args[0]["stderr"] == "boom"


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

    assert result["changed"] is True
    assert result["target"] == "cargo-nextest@0.9.100"
    assert result["cmd"] == [
        "/usr/bin/cargo",
        "binstall",
        "--no-confirm",
        "--force",
        "cargo-nextest@0.9.100",
    ]


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

    assert result["changed"] is True
    assert result["cmd"] == [
        "/usr/bin/cargo",
        "uninstall",
        "--package",
        "cargo-nextest",
        "--root",
        "/opt/cargo-tools",
    ]


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

    assert uv_tool.read_installed_tools(FakeModule(), "/usr/bin/uv") == {
        "ruff": "0.14.0",
        "nixie": "0.1.0",
    }


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

    assert result["changed"] is True
    assert result["target"] == "ruff==0.14.0"
    assert result["cmd"] == [
        "/usr/bin/uv",
        "tool",
        "install",
        "--force",
        "--python",
        "3.12",
        "--with",
        "pytest",
        "ruff==0.14.0",
    ]


def test_uv_tool_uses_spec_over_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uv_tool, "resolve_binary", lambda module, value: "/usr/bin/uv")
    monkeypatch.setattr(uv_tool, "read_installed_tools", lambda module, uv_bin: {})

    result = run_module(
        uv_tool,
        {
            "_ansible_check_mode": True,
            "name": "nixie",
            "version": "1.2.3",
            "spec": "git+https://example.test/nixie",
        },
    )

    assert result["target"] == "git+https://example.test/nixie"
    assert result["cmd"][-1] == "git+https://example.test/nixie"
