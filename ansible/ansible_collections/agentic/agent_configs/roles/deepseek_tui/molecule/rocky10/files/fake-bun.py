#!/usr/bin/env python3
"""Fake Bun executable for the DeepSeek-TUI Molecule scenario."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path


def append_log(argv: list[str]) -> None:
    """Append one fake Bun invocation to the configured JSONL log."""
    log_path = Path(os.environ["BUN_FAKE_LOG"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "argv": argv,
        "BUN_INSTALL_GLOBAL_DIR": os.environ.get("BUN_INSTALL_GLOBAL_DIR"),
        "BUN_INSTALL_BIN": os.environ.get("BUN_INSTALL_BIN"),
        "PATH": os.environ.get("PATH"),
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def write_executable(path: Path) -> None:
    """Write a minimal executable shell shim."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_package(argv: list[str]) -> int:
    """Install fake DeepSeek-TUI package metadata and command shims."""
    global_dir = Path(os.environ["BUN_INSTALL_GLOBAL_DIR"])
    global_bin_dir = Path(os.environ["BUN_INSTALL_BIN"])
    package_json = global_dir / "node_modules" / "deepseek-tui" / "package.json"
    package_json.parent.mkdir(parents=True, exist_ok=True)
    package_json.write_text(
        json.dumps(
            {
                "name": "deepseek-tui",
                "version": argv[-1].rsplit("@", maxsplit=1)[-1],
                "bin": {
                    "deepseek": "bin/deepseek.js",
                    "deepseek-tui": "bin/deepseek-tui.js",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_executable(global_bin_dir / "deepseek")
    write_executable(global_bin_dir / "deepseek-tui")
    return 0


def trust_package() -> int:
    """Record fake trusted dependency metadata."""
    global_dir = Path(os.environ["BUN_INSTALL_GLOBAL_DIR"])
    package_json = global_dir / "package.json"
    package_json.parent.mkdir(parents=True, exist_ok=True)
    package_json.write_text(
        json.dumps({"trustedDependencies": ["deepseek-tui"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


def main() -> int:
    """Dispatch supported fake Bun commands."""
    argv = sys.argv[1:]
    append_log(argv)
    if len(argv) >= 3 and argv[:2] == ["install", "-g"]:
        return install_package(argv)
    if argv == ["pm", "trust", "deepseek-tui"]:
        return trust_package()
    print(f"unsupported fake bun invocation: {argv}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
