"""Shared helpers for Bun global package Ansible modules."""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ansible.module_utils.basic import AnsibleModule


def resolve_binary(module: "AnsibleModule", value: str) -> str:
    """Resolve and return the path to a named Bun binary."""
    path = module.get_bin_path(value, required=False)
    if path:
        return path
    module.fail_json(msg=f"Could not find executable: {value}")
    raise SystemExit


def run(
    module: "AnsibleModule",
    cmd: list[str],
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """Run a command using the Ansible module runner and return its output."""
    rc, stdout, stderr = module.run_command(cmd, environ_update=env or {}, cwd=cwd)
    return rc, stdout, stderr


def package_json_path(global_dir: str | Path, package_name: str) -> str:
    """Return the package.json path for a global Bun package."""
    return str(
        Path(global_dir).joinpath(
            "node_modules", *package_name.split("/"), "package.json"
        )
    )


def read_installed_version(pkg_json: str | Path) -> str | None:
    """Read the installed version from a package.json file."""
    path = Path(pkg_json)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("version")


def is_trusted_dependency(global_dir: str | Path, package_name: str) -> bool:
    """Return True if the package is listed as a trusted dependency."""
    pkg_json = Path(global_dir) / "package.json"
    if not pkg_json.exists():
        return False
    with open(pkg_json, encoding="utf-8") as fh:
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


def build_bun_env(global_dir: str | Path, global_bin_dir: str | Path) -> dict[str, str]:
    """Return the environment needed by Bun and Bun-run package scripts."""
    path = os.environ.get("PATH", "")
    global_dir_value = str(global_dir)
    global_bin_dir_value = str(global_bin_dir)
    return {
        "BUN_INSTALL_GLOBAL_DIR": global_dir_value,
        "BUN_INSTALL_BIN": global_bin_dir_value,
        "PATH": f"{global_bin_dir_value}:{path}" if path else global_bin_dir_value,
    }
