"""Shared helpers for Bun global package Ansible modules."""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ansible.module_utils.basic import AnsibleModule


def resolve_binary(module: "AnsibleModule", value: str) -> str:
    """Resolve the path to a named Bun binary.

    Parameters
    ----------
    module : AnsibleModule
        Module instance used to resolve executable paths and report failures.
    value : str
        Bun executable path or command name.

    Returns
    -------
    str
        Resolved executable path.
    """
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
    """Run a command through the Ansible module runner.

    Parameters
    ----------
    module : AnsibleModule
        Module instance used to execute the command.
    cmd : list[str]
        Command and arguments to execute.
    env : dict[str, str] | None
        Optional environment overrides.
    cwd : str | None
        Optional working directory.

    Returns
    -------
    tuple[int, str, str]
        Return code, standard output, and standard error.
    """
    rc, stdout, stderr = module.run_command(cmd, environ_update=env or {}, cwd=cwd)
    return rc, stdout, stderr


def package_json_path(global_dir: str | Path, package_name: str) -> Path:
    """Build the package metadata path for a global Bun package.

    Parameters
    ----------
    global_dir : str | Path
        Bun global installation directory.
    package_name : str
        Package name installed under ``node_modules``.

    Returns
    -------
    Path
        Path to the package's ``package.json`` file.
    """
    return Path(global_dir) / "node_modules" / package_name / "package.json"


def read_installed_version(pkg_json: Path) -> str | None:
    """Read the installed version from package metadata.

    Parameters
    ----------
    pkg_json : Path
        Path to a package ``package.json`` file.

    Returns
    -------
    str | None
        Installed package version, or ``None`` when metadata is absent.
    """
    if not pkg_json.exists():
        return None
    with pkg_json.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("version")


def is_trusted_dependency(global_dir: str | Path, package_name: str) -> bool:
    """Return whether a package is trusted for post-install scripts.

    Parameters
    ----------
    global_dir : str | Path
        Bun global installation directory.
    package_name : str
        Package name to check in trusted dependency metadata.

    Returns
    -------
    bool
        ``True`` when the package is listed as trusted.
    """
    pkg_json = Path(global_dir) / "package.json"
    if not pkg_json.exists():
        return False
    with pkg_json.open(encoding="utf-8") as fh:
        data = json.load(fh)
    trusted_dependencies = data.get("trustedDependencies", [])
    return (
        isinstance(trusted_dependencies, list) and package_name in trusted_dependencies
    )


def trust_result_is_idempotent(stderr: str) -> bool:
    """Return whether Bun trust output means no work was needed.

    Parameters
    ----------
    stderr : str
        Standard error emitted by ``bun pm trust``.

    Returns
    -------
    bool
        ``True`` when Bun reported an already-idempotent trust result.
    """
    return "0 scripts ran" in stderr and (
        "already trusted" in stderr or "don't have scripts to run" in stderr
    )


def build_bun_env(global_dir: str | Path, global_bin_dir: str | Path) -> dict[str, str]:
    """Build the environment used by Bun lifecycle commands.

    Parameters
    ----------
    global_dir : str | Path
        Bun global installation directory.
    global_bin_dir : str | Path
        Bun global binary directory.

    Returns
    -------
    dict[str, str]
        Environment variables for Bun global installs and trusted scripts.
    """
    path = os.environ.get("PATH", "")
    global_dir_value = str(global_dir)
    global_bin_dir_value = str(global_bin_dir)
    return {
        "BUN_INSTALL_GLOBAL_DIR": global_dir_value,
        "BUN_INSTALL_BIN": global_bin_dir_value,
        "PATH": f"{global_bin_dir_value}:{path}" if path else global_bin_dir_value,
    }
