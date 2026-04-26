# -*- coding: utf-8 -*-
"""Shared path resolution helpers for Bun Ansible modules."""

from __future__ import annotations

import os


def expand_home(path: str) -> str:
    if path == "~":
        return os.environ.get("HOME", path)
    if path.startswith("~/"):
        return os.path.join(os.environ.get("HOME", "~"), path[2:])
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
