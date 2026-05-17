#!/usr/bin/env python3
"""Fake uv executable for deterministic uv_tools Molecule tests."""

from __future__ import annotations

import json
import os
import pathlib
import stat
import sys

TOOL_DIR = pathlib.Path("/root/.local/bin")
STATE_PATH = pathlib.Path("/tmp/fake-uv-log/installed-tools.json")


def log_command(argv: list[str]) -> None:
    """Append the fake uv invocation to the command log."""
    log_path = pathlib.Path(
        os.environ.get("UV_FAKE_LOG", "/tmp/fake-uv-log/uv-commands.jsonl")
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"argv": argv, "PATH": os.environ.get("PATH", "")}
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry) + "\n")


def read_installed_tools() -> dict[str, str]:
    """Read fake uv tool state from disk."""
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def write_installed_tools(installed_tools: dict[str, str]) -> None:
    """Persist fake uv tool state to disk."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(installed_tools, sort_keys=True), encoding="utf-8")


def tool_name_from_target(target: str) -> str:
    """Return the uv tool name represented by an install target."""
    normalized_target = target.rstrip("/")
    return normalized_target.rsplit("/", maxsplit=1)[-1].split("==", maxsplit=1)[0]


def install_tool(target: str) -> None:
    """Record a fake uv tool install and create its executable shim."""
    tool_name = tool_name_from_target(target)
    installed_tools = read_installed_tools()
    installed_tools[tool_name] = "1.0.0"
    write_installed_tools(installed_tools)

    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    shim_path = TOOL_DIR / tool_name
    shim_path.write_text(
        f"#!/usr/bin/env sh\nprintf '%s fake uv tool\\n' {tool_name!r}\n",
        encoding="utf-8",
    )
    shim_path.chmod(
        shim_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )


def main() -> int:
    """Run the fake uv command."""
    argv = sys.argv[1:]
    log_command(argv)

    if argv == ["tool", "list"]:
        for name, version in sorted(read_installed_tools().items()):
            print(f"{name} v{version}")
        return 0

    if len(argv) >= 3 and argv[:2] == ["tool", "install"]:
        install_tool(argv[-1])
        return 0

    if len(argv) == 3 and argv[:2] == ["tool", "uninstall"]:
        installed_tools = read_installed_tools()
        installed_tools.pop(argv[2], None)
        write_installed_tools(installed_tools)
        return 0

    print(f"unsupported fake uv invocation: {argv}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
