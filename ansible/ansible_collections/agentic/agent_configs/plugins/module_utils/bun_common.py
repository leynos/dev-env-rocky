"""Shared helpers for Bun global package Ansible modules."""

from __future__ import annotations

import json
import os
from typing import Any


def resolve_binary(module: Any, value: str) -> str:
    """Resolve and return the path to a named Bun binary."""
    path = module.get_bin_path(value, required=False)
    if path:
        return path
    module.fail_json(msg=f"Could not find executable: {value}")


def run(
    module: Any,
    cmd: list[str],
    env: dict[str, str] | None = None,
    cwd: str | None = None,
):
    """Run a command using the Ansible module runner and return its output."""
    rc, stdout, stderr = module.run_command(cmd, environ_update=env or {}, cwd=cwd)
    return rc, stdout, stderr


def package_json_path(global_dir: str, package_name: str) -> str:
    """Return the package.json path for a global Bun package."""
    return os.path.join(
        global_dir, "node_modules", *package_name.split("/"), "package.json"
    )


def read_installed_version(pkg_json: str) -> str | None:
    """Read the installed version from a package.json file."""
    if not os.path.exists(pkg_json):
        return None
    with open(pkg_json, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("version")


def is_trusted_dependency(global_dir: str, package_name: str) -> bool:
    """Return True if the package is listed as a trusted dependency."""
    pkg_json = os.path.join(global_dir, "package.json")
    if not os.path.exists(pkg_json):
        return False
    with open(pkg_json, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    trusted_dependencies = data.get("trustedDependencies", [])
    return (
        isinstance(trusted_dependencies, list) and package_name in trusted_dependencies
    )


def trust_result_is_idempotent(stderr: str) -> bool:
    """Return True for Bun trust output that means no work was needed."""
    return "0 scripts ran" in stderr and (
        "already trusted" in stderr or "don't have scripts to run" in stderr
    )


def build_bun_env(global_dir: str, global_bin_dir: str) -> dict[str, str]:
    """Return the environment needed by Bun and Bun-run package scripts."""
    path = os.environ.get("PATH", "")
    return {
        "BUN_INSTALL_GLOBAL_DIR": global_dir,
        "BUN_INSTALL_BIN": global_bin_dir,
        "PATH": f"{global_bin_dir}:{path}" if path else global_bin_dir,
    }
