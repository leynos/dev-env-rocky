# -*- coding: utf-8 -*-
"""Shared path resolution helpers for Bun Ansible modules."""

from __future__ import annotations

import os
from pathlib import Path


def expand_home(path: str) -> str:
    try:
        return str(Path(path).expanduser())
    except RuntimeError:
        return path


def resolve_global_dir(param_value: str | None) -> str:
    if param_value:
        return expand_home(param_value)
    env_value = os.environ.get("BUN_INSTALL_GLOBAL_DIR")
    if env_value:
        return expand_home(env_value)
    return expand_home("~/.bun/install/global")


def resolve_global_bin_dir(param_value: str | None) -> str:
    if param_value:
        return expand_home(param_value)
    env_value = os.environ.get("BUN_INSTALL_BIN")
    if env_value:
        return expand_home(env_value)
    return expand_home("~/.bun/bin")
