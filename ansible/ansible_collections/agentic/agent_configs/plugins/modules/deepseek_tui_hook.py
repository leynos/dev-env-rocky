#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Manage DeepSeek-TUI lifecycle hooks in config.toml.

This module performs read-modify-write updates on ``config.toml``. Serialise
parallel writes externally, for example by running the play with ``serial: 1``
when several hosts or tasks can target the same file.
"""

from __future__ import annotations

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    expand_path,
    load_toml_file,
    log_operation,
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


def build_hook_definition(
    *,
    event: str,
    command: str,
    name: str | None,
    condition: dict[str, object] | None,
    timeout_secs: int | None,
    background: bool | None,
    continue_on_error: bool | None,
    extra: dict[str, object],
) -> dict[str, object]:
    """Build a DeepSeek-TUI hook definition from domain parameters."""
    desired: dict[str, object] = {
        "event": event,
        "command": command,
        "name": name,
        "condition": condition,
        "timeout_secs": timeout_secs,
        "background": background,
        "continue_on_error": continue_on_error,
    }
    desired.update(extra)
    return clean_dict(desired)


def hook_identity_matches(
    existing: dict[str, object], desired: dict[str, object]
) -> bool:
    """Return whether two hook entries represent the same managed hook."""
    if existing.get("event") != desired.get("event"):
        return False
    if desired.get("name") is not None or existing.get("name") is not None:
        return existing.get("name") == desired.get("name")
    return existing.get("command") == desired.get("command")


def hook_without_managed_identity(
    hook: object, desired: dict[str, object]
) -> bool:
    """Return whether an existing hook should be retained."""
    return not (isinstance(hook, dict) and hook_identity_matches(hook, desired))


def apply_global_hook_options(
    hooks_root: dict[str, object],
    *,
    enabled: bool | None,
    default_timeout_secs: int | None,
    working_dir: str | None,
) -> bool:
    """Apply optional global DeepSeek-TUI hook settings."""
    changed = False
    for param_name, value in (
        ("enabled", enabled),
        ("default_timeout_secs", default_timeout_secs),
        ("working_dir", working_dir),
    ):
        if value is None:
            continue
        if hooks_root.get(param_name) != value:
            hooks_root[param_name] = value
            changed = True
    return changed


def ensure_hook_toml_shape(path: str, data: object) -> dict[str, object]:
    """Return a mutable TOML root object or raise a contextual validation error."""
    if not isinstance(data, dict):
        raise ValueError(f"Expected TOML root object path={path!r}")
    return data


def ensure_hooks_root(path: str, data: dict[str, object]) -> dict[str, object]:
    """Return the mutable DeepSeek-TUI hooks table."""
    hooks_root = data.setdefault("hooks", {})
    if not isinstance(hooks_root, dict):
        raise ValueError(f"Expected 'hooks' to be a table path={path!r}")
    return hooks_root


def ensure_hook_entries(path: str, hooks_root: dict[str, object]) -> list[object]:
    """Return the mutable hook entry list."""
    hook_entries = hooks_root.setdefault("hooks", [])
    if not isinstance(hook_entries, list):
        raise ValueError(f"Expected 'hooks.hooks' to be a list path={path!r}")
    return hook_entries


def manage_hook_toml(
    module: AnsibleModule,
    path: str,
    desired_hook: dict[str, object],
    state: str,
) -> tuple[bool, dict[str, object], bool]:
    """Create, update, or remove one DeepSeek-TUI hook in a TOML config file."""
    path = expand_path(path)
    data, removed_legacy_block = load_toml_file(module, path, default={})
    data = ensure_hook_toml_shape(path, data)
    hooks_root = ensure_hooks_root(path, data)
    hook_entries = ensure_hook_entries(path, hooks_root)

    existed_before = any(
        isinstance(hook, dict) and hook_identity_matches(hook, desired_hook)
        for hook in hook_entries
    )
    changed = apply_global_hook_options(
        hooks_root,
        enabled=module.params.get("enabled"),
        default_timeout_secs=module.params.get("default_timeout_secs"),
        working_dir=module.params.get("working_dir"),
    )

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
            return True, data, existed_before
        write_toml_if_changed(module, path, data)
    return changed, data, existed_before


def state_transition(changed: bool, existed_before: bool, state: str) -> str:
    """Return a compact state transition label for module results."""
    if not changed:
        return "unchanged"
    if state == "absent":
        return "removed" if existed_before else "unchanged"
    return "updated" if existed_before else "created"


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
        module.fail_json(
            msg=(
                "failed to resolve DeepSeek-TUI hook path "
                f"event={module.params.get('event')!r} "
                f"name={module.params.get('name')!r} "
                f"scope={module.params.get('scope')!r}: {exc}"
            )
        )

    desired = build_hook_definition(
        event=module.params["event"],
        command=module.params["command"],
        name=module.params.get("name"),
        condition=module.params.get("condition"),
        timeout_secs=module.params.get("timeout_secs"),
        background=module.params.get("background"),
        continue_on_error=module.params.get("continue_on_error"),
        extra=module.params.get("extra") or {},
    )
    try:
        changed, data, existed_before = manage_hook_toml(
            module=module,
            path=path,
            desired_hook=desired,
            state=module.params["state"],
        )
    except ValueError as exc:
        module.fail_json(
            msg=(
                "failed to manage DeepSeek-TUI hook "
                f"path={path!r} event={module.params.get('event')!r} "
                f"name={module.params.get('name')!r} "
                f"state={module.params.get('state')!r}: {exc}"
            )
        )

    transition = state_transition(changed, existed_before, module.params["state"])
    log_operation(
        module,
        "deepseek_tui_hook",
        action=transition,
        path=path,
        event=module.params["event"],
        name=module.params.get("name"),
        scope=module.params["scope"],
        state=module.params["state"],
        changed=changed,
    )
    module.exit_json(
        changed=changed,
        path=path,
        scope=module.params["scope"],
        event=module.params["event"],
        command=module.params["command"],
        hook=desired if module.params["state"] == "present" else None,
        hooks=data.get("hooks", {}),
        state_transition=transition,
    )


if __name__ == "__main__":
    main()
