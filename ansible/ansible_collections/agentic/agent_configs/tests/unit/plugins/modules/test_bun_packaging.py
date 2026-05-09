"""Test agentic Bun packaging helpers.

This module exercises the agentic ``bun_global`` module and shared Bun path
resolution helpers through an in-process Ansible harness. Run it with:

    PYTHONPATH=ansible pytest \
        ansible/ansible_collections/agentic/agent_configs/tests/unit/plugins/modules/test_bun_packaging.py
"""

from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
from typing import Any, Callable

import pytest

from ansible_collections.agentic.agent_configs.plugins.module_utils import bun_paths
from ansible_collections.agentic.agent_configs.plugins.modules import bun_global
from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    AnsibleExitJson,
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


def test_bun_package_json_path_handles_scoped_packages() -> None:
    assert_equal(
        bun_global.package_json_path(Path("/global"), "@scope/tool"),
        Path("/global/node_modules/@scope/tool/package.json"),
        "bun_global.package_json_path should handle scoped package paths",
    )


def test_bun_read_installed_version(tmp_path: Path) -> None:
    package_json = tmp_path / "package.json"

    assert_is(
        bun_global.read_installed_version(package_json),
        None,
        "bun_global.read_installed_version should return None for missing metadata",
    )

    package_json.write_text(json.dumps({"version": "1.2.3"}))

    assert_equal(
        bun_global.read_installed_version(package_json),
        "1.2.3",
        "bun_global.read_installed_version should read package version",
    )


def test_bun_is_trusted_dependency(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    package_json = global_dir / "package.json"

    assert_is(
        bun_global.is_trusted_dependency(global_dir, "@scope/tool"),
        False,
        "bun_global.is_trusted_dependency should return False without package metadata",
    )

    package_json.write_text(json.dumps({"trustedDependencies": ["@scope/tool"]}))

    assert_is(
        bun_global.is_trusted_dependency(global_dir, "@scope/tool"),
        True,
        "bun_global.is_trusted_dependency should detect trusted package",
    )


def test_bun_build_env_adds_global_bin_dir_to_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controlled_path = "/usr/local/bin:/usr/bin"
    monkeypatch.setenv("PATH", controlled_path)
    global_bin_dir = tmp_path / "bin"

    env = bun_global.build_bun_env(tmp_path / "global", global_bin_dir)

    assert_equal(
        env["PATH"],
        f"{global_bin_dir!s}:{controlled_path}",
        "bun_global should expose Bun shims to package lifecycle scripts",
    )


def test_bun_expand_home_uses_home_for_tilde(monkeypatch: pytest.MonkeyPatch) -> None:
    home = "/tmp/test-home"
    monkeypatch.setenv("HOME", home)

    assert_equal(
        bun_paths.expand_home("~"),
        home,
        "bun_paths.expand_home should expand bare tilde",
    )
    assert_equal(
        bun_paths.expand_home("~/projects"),
        str(Path(home) / "projects"),
        "bun_paths.expand_home should expand tilde-prefixed paths",
    )


def test_bun_expand_home_uses_system_home_when_home_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_bun_expand_home_preserves_expanduser_user_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


@pytest.mark.parametrize(
    ("resolver", "env_var_name", "env_value", "explicit_param", "expected_suffix"),
    [
        (
            bun_paths.resolve_global_dir,
            "BUN_INSTALL_GLOBAL_DIR",
            "~/bun-global",
            None,
            "bun-global",
        ),
        (
            bun_paths.resolve_global_dir,
            "BUN_INSTALL_GLOBAL_DIR",
            "~/ignored-global",
            "~/explicit-global",
            "explicit-global",
        ),
        (
            bun_paths.resolve_global_bin_dir,
            "BUN_INSTALL_BIN",
            "~/bun-bin",
            None,
            "bun-bin",
        ),
        (
            bun_paths.resolve_global_bin_dir,
            "BUN_INSTALL_BIN",
            "~/ignored-bin",
            "~/explicit-bin",
            "explicit-bin",
        ),
    ],
)
def test_bun_path_resolvers_follow_precedence(
    monkeypatch: pytest.MonkeyPatch,
    resolver: Callable[[str | None], str],
    env_var_name: str,
    env_value: str,
    explicit_param: str | None,
    expected_suffix: str,
) -> None:
    home = "/tmp/test-home"
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv(env_var_name, env_value)

    assert_equal(
        resolver(explicit_param),
        str(Path(home) / expected_suffix),
        f"{resolver.__name__} should prefer explicit value, then {env_var_name}",
    )


def test_bun_global_check_mode_installs_missing_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bun_global, "resolve_binary", lambda module, value: "/usr/bin/bun"
    )
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
    assert_equal(
        result["target"],
        "@scope/tool@1.2.3",
        "bun_global should build versioned target",
    )
    assert_equal(
        result["cmd"],
        ["/usr/bin/bun", "install", "-g", "--ignore-scripts", "@scope/tool@1.2.3"],
        "bun_global should build install command with ignore scripts",
    )


def test_bun_global_check_mode_installs_explicit_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bun_global, "resolve_binary", lambda module, value: "/usr/bin/bun"
    )
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
            "name": "css-view",
            "spec": "git+https://github.com/leynos/css-view#26b79e8ab739b7a8bcd80341ae7fc2d18600ce85",
            "global_dir": str(tmp_path / "global"),
            "global_bin_dir": str(tmp_path / "bin"),
        },
    )

    assert_equal(
        result["target"],
        "git+https://github.com/leynos/css-view#26b79e8ab739b7a8bcd80341ae7fc2d18600ce85",
        "bun_global should use explicit install specs as the target",
    )
    assert_equal(
        result["cmd"],
        [
            "/usr/bin/bun",
            "install",
            "-g",
            "git+https://github.com/leynos/css-view#26b79e8ab739b7a8bcd80341ae7fc2d18600ce85",
        ],
        "bun_global should install from the explicit spec",
    )


def test_bun_global_check_mode_trusts_missing_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bun_global, "resolve_binary", lambda module, value: "/usr/bin/bun"
    )
    monkeypatch.setattr(bun_global, "read_installed_version", lambda path: None)
    monkeypatch.setattr(
        bun_global,
        "run",
        lambda module, cmd, env=None, cwd=None: pytest.fail(
            "check mode must not run bun"
        ),
    )

    result = run_module(
        bun_global,
        {
            "_ansible_check_mode": True,
            "name": "@ataraxy-labs/sem",
            "global_dir": str(tmp_path / "global"),
            "global_bin_dir": str(tmp_path / "bin"),
            "trust_postinstall": True,
        },
    )

    assert_is(
        result["changed"], True, "bun_global should report trusted install change"
    )
    assert_equal(
        result["cmd"],
        ["/usr/bin/bun", "install", "-g", "@ataraxy-labs/sem"],
        "bun_global should build sem install command",
    )
    assert_equal(
        result["trust_cmd"],
        ["/usr/bin/bun", "pm", "trust", "@ataraxy-labs/sem"],
        "bun_global should build sem trust command",
    )


def test_bun_global_install_passes_resolved_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controlled_path = "/usr/local/bin:/usr/bin"
    monkeypatch.setenv("PATH", controlled_path)
    recorded: dict[str, Any] = {}

    def fake_run(
        module: Any,
        cmd: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> tuple[int, str, str]:
        recorded["cmd"] = cmd
        recorded["env"] = env
        recorded["cwd"] = cwd
        return 0, "installed", ""

    monkeypatch.setattr(
        bun_global, "resolve_binary", lambda module, value: "/usr/bin/bun"
    )
    monkeypatch.setattr(bun_global, "read_installed_version", lambda path: None)
    monkeypatch.setattr(bun_global, "run", fake_run)

    global_dir = str(tmp_path / "global")
    global_bin_dir = str(tmp_path / "bin")
    result = run_module(
        bun_global,
        {
            "name": "tool",
            "version": "1.2.3",
            "global_dir": global_dir,
            "global_bin_dir": global_bin_dir,
        },
    )

    assert_equal(
        result["target"], "tool@1.2.3", "bun_global should build versioned target"
    )
    assert_equal(
        recorded["cmd"],
        ["/usr/bin/bun", "install", "-g", "tool@1.2.3"],
        "bun_global should execute install command",
    )
    assert_equal(
        recorded["env"],
        {
            "BUN_INSTALL_GLOBAL_DIR": global_dir,
            "BUN_INSTALL_BIN": global_bin_dir,
            "PATH": f"{global_bin_dir}:{controlled_path}",
        },
        "bun_global should pass resolved Bun paths to subprocess environment",
    )
    assert_is(recorded["cwd"], None, "bun_global install should not override cwd")


def test_bun_global_trusts_installed_package_without_reinstalling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controlled_path = "/usr/local/bin:/usr/bin"
    monkeypatch.setenv("PATH", controlled_path)
    recorded: dict[str, Any] = {}

    def fake_run(
        module: Any,
        cmd: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> tuple[int, str, str]:
        recorded["cmd"] = cmd
        recorded["env"] = env
        recorded["cwd"] = cwd
        return 0, "trusted", ""

    monkeypatch.setattr(
        bun_global, "resolve_binary", lambda module, value: "/usr/bin/bun"
    )
    monkeypatch.setattr(bun_global, "read_installed_version", lambda path: "1.2.3")
    monkeypatch.setattr(bun_global, "run", fake_run)

    global_dir = tmp_path / "global"
    global_dir.mkdir()
    (global_dir / "package.json").write_text(
        json.dumps({"dependencies": {"tool": "1.2.3"}})
    )
    global_bin_dir = str(tmp_path / "bin")
    result = run_module(
        bun_global,
        {
            "name": "tool",
            "version": "1.2.3",
            "global_dir": str(global_dir),
            "global_bin_dir": global_bin_dir,
            "trust_postinstall": True,
        },
    )

    assert_equal(
        recorded["cmd"],
        ["/usr/bin/bun", "pm", "trust", "tool"],
        "bun_global should trust installed package without reinstalling",
    )
    assert_equal(
        recorded["env"],
        {
            "BUN_INSTALL_GLOBAL_DIR": str(global_dir),
            "BUN_INSTALL_BIN": global_bin_dir,
            "PATH": f"{global_bin_dir}:{controlled_path}",
        },
        "bun_global should pass resolved Bun paths to trust command",
    )
    assert_equal(
        recorded["cwd"],
        str(global_dir),
        "bun_global should run trust in global install dir",
    )
    assert_equal(
        result["trust_cmd"],
        ["/usr/bin/bun", "pm", "trust", "tool"],
        "bun_global should report trust command",
    )


def test_bun_global_treats_zero_script_trust_result_as_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        module: Any,
        cmd: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> tuple[int, str, str]:
        return (
            1,
            "",
            "error: 0 scripts ran. The following packages are already trusted, "
            "don't have scripts to run, or don't exist:\n - @scope/tool",
        )

    monkeypatch.setattr(
        bun_global, "resolve_binary", lambda module, value: "/usr/bin/bun"
    )
    monkeypatch.setattr(bun_global, "read_installed_version", lambda path: "1.2.3")
    monkeypatch.setattr(bun_global, "run", fake_run)

    global_dir = tmp_path / "global"
    global_dir.mkdir()
    (global_dir / "package.json").write_text(json.dumps({"dependencies": {}}))
    result = run_module(
        bun_global,
        {
            "name": "@scope/tool",
            "version": "1.2.3",
            "global_dir": str(global_dir),
            "global_bin_dir": str(tmp_path / "bin"),
            "trust_postinstall": True,
        },
    )

    assert_equal(
        result["trust_cmd"],
        ["/usr/bin/bun", "pm", "trust", "@scope/tool"],
        "bun_global should report idempotent trust attempts",
    )
    assert_equal(
        result["trust_stderr"],
        "error: 0 scripts ran. The following packages are already trusted, "
        "don't have scripts to run, or don't exist:\n - @scope/tool",
        "bun_global should preserve idempotent trust stderr for diagnostics",
    )


def test_bun_global_reports_present_package_without_running_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bun_global, "resolve_binary", lambda module, value: "/usr/bin/bun"
    )
    monkeypatch.setattr(bun_global, "read_installed_version", lambda path: "1.2.3")
    monkeypatch.setattr(
        bun_global,
        "run",
        lambda module, cmd, env=None: pytest.fail(
            "installed package must be idempotent"
        ),
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

    assert_equal(
        result,
        {
            "changed": False,
            "name": "tool",
            "state": "present",
            "installed_version": "1.2.3",
            "global_dir": str(tmp_path / "global"),
            "global_bin_dir": str(tmp_path / "bin"),
        },
        "bun_global should be idempotent for installed package",
    )
