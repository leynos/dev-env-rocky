#!/usr/bin/env python3
"""Fake Bun executable used by the node_packages Molecule scenario."""

import json
import os
import stat
import sys
from pathlib import Path


LOG_PATH = Path("/tmp/bun-commands.jsonl")


def package_from_target(target: str) -> tuple[str, str]:
    """Parse an npm target string into a package name and version.

    Parameters
    ----------
    target : str
        Package target passed to ``bun install -g``.

    Returns
    -------
    tuple[str, str]
        Package name and version. Defaults to ``"0.0.0"`` when no version is
        found, treats ``git+https`` css-view targets as ``css-view``, and
        preserves scoped package names that start with ``@``.
    """
    if target.startswith("git+https://github.com/leynos/css-view"):
        return "css-view", "0.0.0"

    if target.startswith("@"):
        package_part, _, version = target.rpartition("@")
        if "/" in package_part and version:
            return package_part, version
        return target, "0.0.0"

    package_part, separator, version = target.rpartition("@")
    if separator and package_part:
        return package_part, version
    return target, "0.0.0"


def package_json_path(global_dir: Path, package_name: str) -> Path:
    """Build the fake global package metadata path.

    Parameters
    ----------
    global_dir : Path
        Bun global installation directory.
    package_name : str
        Package name to locate under ``node_modules``.

    Returns
    -------
    Path
        Path to the package's ``package.json`` file, including scoped package
        path components.
    """
    return global_dir / "node_modules" / Path(*package_name.split("/")) / "package.json"


def write_json(path: Path, data: dict[str, object]) -> None:
    """Write formatted JSON after creating parent directories.

    Parameters
    ----------
    path : Path
        Destination file path.
    data : dict[str, object]
        JSON-serializable mapping to write.

    Returns
    -------
    None
        The function writes the file and returns no value.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def append_log(argv: list[str]) -> None:
    """Append a fake Bun invocation record to the JSONL command log.

    Parameters
    ----------
    argv : list[str]
        Command-line arguments passed to the fake Bun executable.

    Returns
    -------
    None
        The function appends one JSON object to ``LOG_PATH`` and returns no
        value.
    """
    entry = {
        "argv": argv,
        "cwd": os.getcwd(),
        "BUN_INSTALL_GLOBAL_DIR": os.environ.get("BUN_INSTALL_GLOBAL_DIR"),
        "BUN_INSTALL_BIN": os.environ.get("BUN_INSTALL_BIN"),
        "PATH": os.environ.get("PATH"),
    }
    with LOG_PATH.open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry, sort_keys=True) + "\n")


def install_package(argv: list[str]) -> int:
    """Install a fake global package and executable shim.

    Parameters
    ----------
    argv : list[str]
        Bun install arguments, with the target package specifier as the last
        item.

    Returns
    -------
    int
        Process exit code. Returns ``0`` after writing package metadata and
        executable shims.
    """
    target = argv[-1]
    package_name, version = package_from_target(target)
    global_dir = Path(os.environ["BUN_INSTALL_GLOBAL_DIR"])
    global_bin_dir = Path(os.environ["BUN_INSTALL_BIN"])

    write_json(
        package_json_path(global_dir, package_name),
        {
            "name": package_name,
            "version": version,
            "bin": {package_name.split("/")[-1]: "bin/tool.js"},
        },
    )
    global_bin_dir.mkdir(parents=True, exist_ok=True)

    binary_name = package_name.split("/")[-1]
    binary = global_bin_dir / binary_name
    binary.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if package_name == "@typescript/native-preview":
        tsgo = global_bin_dir / "tsgo"
        tsgo.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        tsgo.chmod(tsgo.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return 0


def trust_package(argv: list[str]) -> int:
    """Mark a fake package as trusted for postinstall scripts.

    Parameters
    ----------
    argv : list[str]
        Bun trust arguments, with the package name as the last item.

    Returns
    -------
    int
        Process exit code. Returns ``0`` after updating trusted dependency
        metadata and creating css-view browser cache markers when applicable.
    """
    package_name = argv[-1]
    global_dir = Path(os.environ["BUN_INSTALL_GLOBAL_DIR"])
    package_json = global_dir / "package.json"

    if package_json.exists():
        data = json.loads(package_json.read_text(encoding="utf-8"))
    else:
        data = {}
    trusted = data.setdefault("trustedDependencies", [])
    if package_name not in trusted:
        trusted.append(package_name)
    write_json(package_json, data)

    if package_name == "css-view":
        cache = Path.home() / ".cache" / "ms-playwright"
        for browser_dir in ("chromium-1217", "chromium_headless_shell-1217"):
            (cache / browser_dir).mkdir(parents=True, exist_ok=True)

    return 0


def main() -> int:
    """Dispatch supported fake Bun subcommands.

    Parameters
    ----------
    None
        Reads command-line arguments from ``sys.argv``.

    Returns
    -------
    int
        Process exit code. Returns ``2`` for unsupported fake Bun invocations.
    """
    argv = sys.argv[1:]
    append_log(argv)

    if len(argv) >= 3 and argv[:2] == ["install", "-g"]:
        return install_package(argv)
    if len(argv) == 3 and argv[:2] == ["pm", "trust"]:
        return trust_package(argv)
    if len(argv) == 3 and argv[:2] == ["remove", "-g"]:
        return 0

    print(f"unsupported fake bun invocation: {argv}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
