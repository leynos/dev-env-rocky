"""Resolve Bun global installation paths for Ansible modules.

This module exposes shared helpers used by the agentic and packaging Bun
modules. Call ``expand_home`` for shell-style home expansion, then use
``resolve_global_dir`` or ``resolve_global_bin_dir`` to derive the effective
Bun global package and binary directories from an explicit module parameter,
the relevant environment variable, or the repository default.

Example
-------
``resolve_global_dir("~/tools/bun-global")`` returns the expanded absolute
home-relative path for the caller's configured global package directory.
"""

from __future__ import annotations

import os
from pathlib import Path


def expand_home(path: str) -> str:
    try:
        return str(Path(path).expanduser())
    except RuntimeError:
        return path


def resolve_global_dir(param_value: str | None) -> str:
    """Resolve the Bun global package directory.

    Parameters
    ----------
    param_value : str or None
        Explicit Ansible module parameter. When provided, this value takes
        precedence over environment variables and defaults.

    Returns
    -------
    str
        The resolved path after expanding ``~`` where possible.

    Notes
    -----
    Precedence is ``param_value``, then ``BUN_INSTALL_GLOBAL_DIR``, then the
    default ``~/.bun/install/global`` path.
    """
    if param_value:
        return expand_home(param_value)
    env_value = os.environ.get("BUN_INSTALL_GLOBAL_DIR")
    if env_value:
        return expand_home(env_value)
    return expand_home("~/.bun/install/global")


def resolve_global_bin_dir(param_value: str | None) -> str:
    """Resolve the Bun global binary directory.

    Parameters
    ----------
    param_value : str or None
        Explicit Ansible module parameter. When provided, this value takes
        precedence over environment variables and defaults.

    Returns
    -------
    str
        The resolved path after expanding ``~`` where possible.

    Notes
    -----
    Precedence is ``param_value``, then ``BUN_INSTALL_BIN``, then the default
    ``~/.bun/bin`` path.
    """
    if param_value:
        return expand_home(param_value)
    env_value = os.environ.get("BUN_INSTALL_BIN")
    if env_value:
        return expand_home(env_value)
    return expand_home("~/.bun/bin")
