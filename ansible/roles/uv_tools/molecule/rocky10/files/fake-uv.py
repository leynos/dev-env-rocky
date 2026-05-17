#!/usr/bin/env python3
"""Fake uv executable for deterministic uv_tools Molecule tests."""

import fcntl
import json
import os
import pathlib
import stat
import sys
from collections.abc import Callable

TOOL_DIR = pathlib.Path("/root/.local/bin")
STATE_PATH = pathlib.Path("/tmp/fake-uv-log/installed-tools.json")


def _log_command(argv: list[str]) -> None:
    """Append the fake uv invocation to the command log."""
    log_path = pathlib.Path(
        os.environ.get("UV_FAKE_LOG", "/tmp/fake-uv-log/uv-commands.jsonl")
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"argv": argv, "PATH": os.environ.get("PATH", "")}
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry) + "\n")


def _read_installed_tools() -> dict[str, str]:
    """Read fake uv tool state from disk."""
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _write_installed_tools(installed_tools: dict[str, str]) -> None:
    """Persist fake uv tool state to disk."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as state_file:
        state_file.write(json.dumps(installed_tools, sort_keys=True))
        state_file.flush()
        os.fsync(state_file.fileno())
    os.replace(tmp_path, STATE_PATH)


def _locked_state_update(updater_fn: Callable[[dict[str, str]], None]) -> None:
    """Update fake uv state under a lock; Molecule is sequential, but this guards accidents."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = STATE_PATH.with_suffix(".lock")
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            installed_tools = _read_installed_tools()
            updater_fn(installed_tools)
            _write_installed_tools(installed_tools)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _tool_name_from_target(target: str) -> str:
    """Return the uv tool name represented by an install target."""
    normalized_target = target.rstrip("/")
    return normalized_target.rsplit("/", maxsplit=1)[-1].split("==", maxsplit=1)[0]


def _requested_executables_from(argv: list[str]) -> list[str]:
    """Return package names requested with uv's executable-linking flag."""
    packages: list[str] = []
    for index, arg in enumerate(argv):
        if arg == "--with-executables-from" and index + 1 < len(argv):
            packages.extend(argv[index + 1].split(","))
    return packages


def _write_shim(tool_name: str) -> None:
    """Create a fake executable shim for a uv-managed command."""
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    shim_path = TOOL_DIR / tool_name
    shim_path.write_text(
        f"#!/usr/bin/env sh\nprintf '%s fake uv tool\\n' {tool_name!r}\n",
        encoding="utf-8",
    )
    shim_path.chmod(
        shim_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )


def _install_tool(argv: list[str]) -> None:
    """Record a fake uv tool install and create executable shims."""
    target = argv[-1]
    tool_name = _tool_name_from_target(target)

    def record_install(installed_tools: dict[str, str]) -> None:
        installed_tools[tool_name] = "1.0.0"

    _locked_state_update(record_install)

    _write_shim(tool_name)
    if "ansible-core" in _requested_executables_from(argv):
        _write_shim("ansible-playbook")


def main() -> int:
    """Run the fake uv command."""
    argv = sys.argv[1:]
    _log_command(argv)

    if argv == ["tool", "list"]:
        for name, version in sorted(_read_installed_tools().items()):
            print(f"{name} v{version}")
        return 0

    if len(argv) >= 3 and argv[:2] == ["tool", "install"]:
        _install_tool(argv)
        return 0

    if len(argv) == 3 and argv[:2] == ["tool", "uninstall"]:

        def record_uninstall(installed_tools: dict[str, str]) -> None:
            installed_tools.pop(argv[2], None)

        _locked_state_update(record_uninstall)
        return 0

    print(f"unsupported fake uv invocation: {argv}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
