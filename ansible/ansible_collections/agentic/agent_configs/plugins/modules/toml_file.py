#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Manage TOML configuration files for the agentic agent_configs collection.

This Ansible module expands the requested ``path`` with ``expand_path``, reads
existing content with ``read_text``, parses and updates nested TOML values, and
persists changed documents with ``atomic_write_text``. Callers provide a target
path, dot-separated key, optional value, state, and mode; the module returns the
managed key and changed status. Side effects are limited to creating, updating,
or chmoding the target TOML file, and expected read, TOML parse, write, and
chmod failures are reported through ``module.fail_json``.
"""

from __future__ import annotations

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    atomic_write_text,
    expand_path,
    read_text,
)

DOCUMENTATION = r"""
---
module: toml_file
short_description: Manage a value inside a TOML file
version_added: "1.0.0"
description:
  - Manage nested values inside a TOML file using C(tomlkit) instead of raw text blocks.
  - Dot-separated keys address nested tables. Escape literal dots as C(\.).
options:
  path:
    description:
      - TOML file to manage.
    type: path
    required: true
  key:
    description:
      - Dot-separated key path to manage.
    type: str
    required: true
  value:
    description:
      - Value to write when C(state=present).
    type: raw
  state:
    description:
      - Whether the key should exist.
    type: str
    choices: [present, absent]
    default: present
  mode:
    description:
      - Optional file mode to enforce after writing or when the file already exists.
    type: str
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Configure Codex environment variable
  agentic.agent_configs.toml_file:
    path: ~/.codex/config.toml
    key: env.RUSTC_WRAPPER
    value: ~/.local/bin/notdeadyet
    mode: '0644'
"""

RETURN = r"""
path:
  description: Managed TOML file path.
  returned: always
  type: str
key:
  description: Managed key path.
  returned: always
  type: str
"""


def import_tomlkit(module: AnsibleModule):
    """Import ``tomlkit`` and its parse error type or fail clearly."""
    try:
        import tomlkit
        from tomlkit.exceptions import ParseError
    except ImportError:
        module.fail_json(
            msg="The toml_file module requires the tomlkit Python package on the target host"
        )
    return tomlkit, ParseError


def split_key_path(key: str) -> list[str]:
    """Split a dot-separated key path while preserving escaped dots.

    Args:
        key: Dot-separated key path such as ``env.SCCACHE_DIR``.

    Returns:
        Path components in traversal order.

    Raises:
        ValueError: If the path contains an empty component.
    """
    parts: list[str] = []
    current: list[str] = []
    escaped = False
    for char in key:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ".":
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if escaped:
        current.append("\\")
    parts.append("".join(current))
    if any(part == "" for part in parts):
        raise ValueError("key must not contain empty path components")
    return parts


def load_document(module: AnsibleModule, tomlkit, parse_error, path: str):
    """Load a TOML document, returning an empty document when absent."""
    content = read_text(path)
    if content is None:
        return tomlkit.document()
    try:
        return tomlkit.parse(content)
    except parse_error as exc:
        module.fail_json(msg="Failed to parse TOML file %s: %s" % (path, exc))


def get_parent(module: AnsibleModule, tomlkit, document, parts: list[str]):
    """Return the parent TOML table for a key path, creating tables as needed."""
    parent = document
    for part in parts[:-1]:
        child = parent.get(part)
        if child is None:
            child = tomlkit.table()
            parent[part] = child
        if not hasattr(child, "get") or not hasattr(child, "__setitem__"):
            module.fail_json(msg="Expected '%s' to be a TOML table" % part)
        parent = child
    return parent


def parse_mode(module: AnsibleModule, mode: str | None) -> int | None:
    """Parse an octal file mode string for ``os.chmod``."""
    if mode is None:
        return None
    try:
        return int(mode, 8)
    except ValueError:
        module.fail_json(msg="mode must be an octal string")


def enforce_mode(module: AnsibleModule, path: str, mode: int | None) -> bool:
    """Apply a parsed file mode when needed and report whether it changed."""
    if mode is None or not os.path.exists(path):
        return False
    current = os.stat(path).st_mode & 0o777
    if current == mode:
        return False
    if not module.check_mode:
        try:
            os.chmod(path, mode)
        except OSError as exc:
            module.fail_json(msg="Failed to chmod TOML file %s: %s" % (path, exc))
    return True


def main() -> None:
    """Run the Ansible module entrypoint."""
    module = AnsibleModule(
        argument_spec={
            "path": {"type": "path", "required": True},
            "key": {"type": "str", "required": True},
            "value": {"type": "raw"},
            "state": {
                "type": "str",
                "choices": ["present", "absent"],
                "default": "present",
            },
            "mode": {"type": "str"},
        },
        supports_check_mode=True,
    )

    tomlkit, parse_error = import_tomlkit(module)
    path = expand_path(module.params["path"])
    try:
        parts = split_key_path(module.params["key"])
    except ValueError as exc:
        module.fail_json(msg=str(exc))
    desired_mode = parse_mode(module, module.params.get("mode"))

    try:
        document = load_document(module, tomlkit, parse_error, path)
    except OSError as exc:
        module.fail_json(msg="Failed to read TOML file %s: %s" % (path, exc))
    parent = get_parent(module, tomlkit, document, parts)
    leaf = parts[-1]
    changed_value = False
    if module.params["state"] == "present":
        if module.params.get("value") is None:
            module.fail_json(msg="value is required when state=present")
        value = module.params.get("value")
        if parent.get(leaf) != value:
            parent[leaf] = value
            changed_value = True
    elif leaf in parent:
        del parent[leaf]
        changed_value = True

    if changed_value and not module.check_mode:
        try:
            atomic_write_text(path, tomlkit.dumps(document))
        except OSError as exc:
            module.fail_json(msg="Failed to write TOML file %s: %s" % (path, exc))
    changed_mode = enforce_mode(module, path, desired_mode)

    module.exit_json(
        changed=(changed_value or changed_mode),
        path=path,
        key=module.params["key"],
        value=parent.get(leaf) if module.params["state"] == "present" else None,
    )


if __name__ == "__main__":
    main()
