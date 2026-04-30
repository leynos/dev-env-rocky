#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import json
import os
from typing import Any

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    atomic_write_text,
    expand_path,
    load_json_file,
)

DOCUMENTATION = r"""
---
module: json_file
short_description: Manage a value inside a JSON object file
version_added: "1.0.0"
description:
  - Manage nested values inside a JSON object file without treating the file as raw text.
  - Dot-separated keys address nested objects. Escape literal dots as C(\.).
options:
  path:
    description:
      - JSON file to manage.
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
- name: Configure Claude Code environment variable
  agentic.agent_configs.json_file:
    path: ~/.claude/settings.json
    key: env.RUSTC_WRAPPER
    value: ~/.local/bin/notdeadyet
    mode: '0644'
"""

RETURN = r"""
path:
  description: Managed JSON file path.
  returned: always
  type: str
key:
  description: Managed key path.
  returned: always
  type: str
"""


def split_key_path(key: str) -> list[str]:
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


def get_parent(
    module: AnsibleModule, data: dict[str, Any], parts: list[str]
) -> dict[str, Any]:
    parent = data
    for part in parts[:-1]:
        child = parent.get(part)
        if child is None:
            child = {}
            parent[part] = child
        if not isinstance(child, dict):
            module.fail_json(msg="Expected '%s' to be a JSON object" % part)
        parent = child
    return parent


def dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def parse_mode(module: AnsibleModule, mode: str | None) -> int | None:
    if mode is None:
        return None
    try:
        return int(mode, 8)
    except ValueError:
        module.fail_json(msg="mode must be an octal string")


def enforce_mode(module: AnsibleModule, path: str, mode: int | None) -> bool:
    if mode is None or not os.path.exists(path):
        return False
    current = os.stat(path).st_mode & 0o777
    if current == mode:
        return False
    if not module.check_mode:
        os.chmod(path, mode)
    return True


def main() -> None:
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

    path = expand_path(module.params["path"])
    try:
        parts = split_key_path(module.params["key"])
    except ValueError as exc:
        module.fail_json(msg=str(exc))
    desired_mode = parse_mode(module, module.params.get("mode"))

    data = load_json_file(path, default={})
    if not isinstance(data, dict):
        module.fail_json(msg="Expected JSON object in %s" % path)

    parent = get_parent(module, data, parts)
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
        atomic_write_text(path, dump_json(data))
    changed_mode = enforce_mode(module, path, desired_mode)

    module.exit_json(
        changed=(changed_value or changed_mode),
        path=path,
        key=module.params["key"],
        value=parent.get(leaf) if module.params["state"] == "present" else None,
    )


if __name__ == "__main__":
    main()
