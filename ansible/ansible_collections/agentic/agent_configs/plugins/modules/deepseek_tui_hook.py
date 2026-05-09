#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Manage DeepSeek-TUI lifecycle hooks in config.toml."""

from __future__ import annotations

import os
from typing import Any

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    expand_path,
    load_toml_file,
    resolve_scoped_config_path,
    write_toml_if_changed,
)

DOCUMENTATION = r"""
---
module: deepseek_tui_hook
short_description: Manage DeepSeek-TUI lifecycle hooks
version_added: "1.0.0"
description:
  - Manage DeepSeek-TUI lifecycle hooks in C(~/.deepseek/config.toml) or C(.deepseek/config.toml).
  - Hooks are stored under the DeepSeek-TUI C([hooks]) table as C([[hooks.hooks]]) entries.
options:
  event:
    description:
      - DeepSeek-TUI hook event name.
    type: str
    required: true
  command:
    description:
      - Shell command to execute for the hook.
    type: str
    required: true
  name:
    description:
      - Optional hook display name.
      - Also participates in hook identity when supplied.
    type: str
  state:
    description:
      - Whether the hook should exist.
    type: str
    choices: [present, absent]
    default: present
  scope:
    description:
      - Configuration scope.
    type: str
    choices: [user, project]
    default: user
  project_dir:
    description:
      - Project root used when C(scope=project).
    type: path
  path:
    description:
      - Exact C(config.toml) path to manage.
      - Overrides C(scope) and C(project_dir).
    type: path
  condition:
    description:
      - Optional DeepSeek-TUI hook condition object.
    type: dict
  timeout_secs:
    description:
      - Hook timeout in seconds.
    type: int
  background:
    description:
      - Run the hook without waiting for completion.
    type: bool
  continue_on_error:
    description:
      - Continue the DeepSeek-TUI lifecycle when this hook fails.
    type: bool
  enabled:
    description:
      - Optional global C([hooks].enabled) value.
    type: bool
  default_timeout_secs:
    description:
      - Optional global C([hooks].default_timeout_secs) value.
    type: int
  working_dir:
    description:
      - Optional global C([hooks].working_dir) value.
    type: path
  extra:
    description:
      - Additional raw keys to merge into the hook definition.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Add a DeepSeek-TUI session-start hook
  agentic.agent_configs.deepseek_tui_hook:
    event: session_start
    name: hello
    command: echo 'DeepSeek TUI session started'

- name: Add a DeepSeek-TUI shell-env hook
  agentic.agent_configs.deepseek_tui_hook:
    event: shell_env
    command: aws-vault export my-profile --format=env
    condition:
      type: tool_category
      category: shell
"""

RETURN = r"""
path:
  description: Managed config path.
  returned: always
  type: str
hook:
  description: Effective hook entry.
  returned: when state == 'present'
  type: dict
"""


def build_hook_definition(module: AnsibleModule) -> dict:
    """Build a DeepSeek-TUI hook definition from module parameters."""
    params = module.params
    desired = {
        "event": params["event"],
        "command": params["command"],
        "name": params.get("name"),
        "condition": params.get("condition"),
        "timeout_secs": params.get("timeout_secs"),
        "background": params.get("background"),
        "continue_on_error": params.get("continue_on_error"),
    }
    desired.update(params.get("extra") or {})
    return clean_dict(desired)


def hook_identity_matches(existing: dict, desired: dict) -> bool:
    """Return whether two hook entries represent the same managed hook."""
    if existing.get("event") != desired.get("event"):
        return False
    if desired.get("name") is not None or existing.get("name") is not None:
        return existing.get("name") == desired.get("name")
    return existing.get("command") == desired.get("command")


def hook_without_managed_identity(hook: Any, desired: dict) -> bool:
    """Return whether an existing hook should be retained."""
    return not (isinstance(hook, dict) and hook_identity_matches(hook, desired))


def apply_global_hook_options(module: AnsibleModule, hooks_root: dict) -> bool:
    """Apply optional global DeepSeek-TUI hook settings."""
    changed = False
    for param_name in ("enabled", "default_timeout_secs", "working_dir"):
        value = module.params.get(param_name)
        if value is None:
            continue
        if hooks_root.get(param_name) != value:
            hooks_root[param_name] = value
            changed = True
    return changed


def manage_hook_toml(
    module: AnsibleModule,
    path: str,
    desired_hook: dict,
    state: str,
) -> tuple[bool, dict]:
    """Create, update, or remove one DeepSeek-TUI hook in a TOML config file."""
    path = expand_path(path)
    data, removed_legacy_block = load_toml_file(module, path, default={})
    if not isinstance(data, dict):
        module.fail_json(msg="Expected TOML root object in %s" % path)
    hooks_root = data.setdefault("hooks", {})
    if not isinstance(hooks_root, dict):
        module.fail_json(msg="Expected 'hooks' to be a table in %s" % path)
    hook_entries = hooks_root.setdefault("hooks", [])
    if not isinstance(hook_entries, list):
        module.fail_json(msg="Expected 'hooks.hooks' to be a list in %s" % path)

    changed = apply_global_hook_options(module, hooks_root)

    if state == "present":
        for index, hook in enumerate(hook_entries):
            if isinstance(hook, dict) and hook_identity_matches(hook, desired_hook):
                if hook != desired_hook:
                    hook_entries[index] = desired_hook
                    changed = True
                break
        else:
            hook_entries.append(desired_hook)
            changed = True
    else:
        retained = [
            hook
            for hook in hook_entries
            if hook_without_managed_identity(hook, desired_hook)
        ]
        if retained != hook_entries:
            hooks_root["hooks"] = retained
            changed = True
        if not hooks_root.get("hooks"):
            hooks_root.pop("hooks", None)
        if not hooks_root:
            data.pop("hooks", None)

    if changed or removed_legacy_block:
        if module.check_mode:
            return True, data
        write_toml_if_changed(module, path, data)
    return changed, data


def main() -> None:
    """Run the Ansible module."""
    module = AnsibleModule(
        argument_spec={
            "event": {"type": "str", "required": True},
            "command": {"type": "str", "required": True},
            "name": {"type": "str"},
            "state": {
                "type": "str",
                "choices": ["present", "absent"],
                "default": "present",
            },
            "scope": {"type": "str", "choices": ["user", "project"], "default": "user"},
            "project_dir": {"type": "path"},
            "path": {"type": "path"},
            "condition": {"type": "dict"},
            "timeout_secs": {"type": "int"},
            "background": {"type": "bool"},
            "continue_on_error": {"type": "bool"},
            "enabled": {"type": "bool"},
            "default_timeout_secs": {"type": "int"},
            "working_dir": {"type": "path"},
            "extra": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )

    try:
        path = resolve_scoped_config_path(
            path=module.params.get("path"),
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path="~/.deepseek/config.toml",
            project_relative_path=os.path.join(".deepseek", "config.toml"),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    desired = build_hook_definition(module)
    changed, data = manage_hook_toml(
        module=module,
        path=path,
        desired_hook=desired,
        state=module.params["state"],
    )

    module.exit_json(
        changed=changed,
        path=path,
        scope=module.params["scope"],
        event=module.params["event"],
        command=module.params["command"],
        hook=desired if module.params["state"] == "present" else None,
        hooks=data.get("hooks", {}),
    )


if __name__ == "__main__":
    main()
