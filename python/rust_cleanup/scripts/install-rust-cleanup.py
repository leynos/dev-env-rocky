#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Install rust-cleanup into a uv-managed virtual environment.

This script provisions a virtual environment with uv and installs the local
``rust-cleanup`` package into it. The ``PYTHON_REQUIREMENT`` constant controls
the interpreter constraint passed to ``uv venv`` so hosts with older
``python3`` binaries can still create a Python 3.12 or newer environment.

Examples
--------
Install the package from a checked-out source tree into a target environment::

    ./install-rust-cleanup.py --source-dir ~/.local/src/rust-cleanup \
        --venv ~/.local/share/rust-cleanup/venv
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

PYTHON_REQUIREMENT = ">=3.12"
SUBPROCESS_TIMEOUT_SECONDS = 900


def run(command: list[str]) -> None:
    """Run a subprocess command with the provisioning timeout.

    Parameters
    ----------
    command : list[str]
        Command and arguments to execute. The command is expected to complete
        successfully within ``SUBPROCESS_TIMEOUT_SECONDS``.

    Returns
    -------
    None
        The function returns after the command exits successfully.

    Raises
    ------
    subprocess.CalledProcessError
        Raised when the command exits with a non-zero status.
    subprocess.TimeoutExpired
        Raised when the command exceeds ``SUBPROCESS_TIMEOUT_SECONDS``.
    """
    subprocess.run(command, check=True, timeout=SUBPROCESS_TIMEOUT_SECONDS)


def main() -> None:
    """Parse command-line arguments and install rust-cleanup.

    Parameters
    ----------
    None
        Arguments are read from the process command line. ``--source-dir``
        points at the package source tree, and ``--venv`` points at the virtual
        environment to create or update.

    Returns
    -------
    None
        The function exits normally after creating the environment and
        installing the package.
    """
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
