#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Install rust-cleanup into a uv-managed virtual environment."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

PYTHON_REQUIREMENT = ">=3.12"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install rust-cleanup into a uv-managed virtual environment.",
    )
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--venv", required=True)
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    venv = Path(args.venv).resolve()
    venv_python = venv / "bin" / "python"

    run(["uv", "venv", "--python", PYTHON_REQUIREMENT, str(venv)])
    run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(venv_python),
            "--upgrade",
            str(source_dir),
        ],
    )


if __name__ == "__main__":
    main()
