#!/usr/bin/python
"""Manage DeepSeek-TUI lifecycle hooks in config.toml.

This module performs read-modify-write updates on ``config.toml``. Serialise
parallel writes externally, for example by running the play with ``serial: 1``
when several hosts or tasks can target the same file.
"""

from pathlib import Path
from typing import Any

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    _state_transition,
    log_operation,
    resolve_scoped_config_path,
)
from ansible_collections.agentic.agent_configs.plugins.module_utils.deepseek_tui_hook_impl import (
    MANAGED_HOOK_FIELDS,
    HookParams,
    build_hook_definition,
    manage_hook_toml,
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


def _build_argument_spec() -> dict[str, Any]:
    """Return the Ansible module argument specification."""
    return {
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
    }


def _resolve_hook_path(module: AnsibleModule) -> str:
    """Resolve the DeepSeek-TUI hook config path."""
    try:
        return resolve_scoped_config_path(
            path=module.params.get("path"),
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path="~/.deepseek/config.toml",
            project_relative_path=str(Path(".deepseek") / "config.toml"),
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


def _apply_hook_changes(
    module: AnsibleModule, path: str, desired: dict[str, Any]
) -> tuple[bool, dict[str, Any], bool]:
    """Apply the desired hook changes to the TOML file."""
    try:
        return manage_hook_toml(
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


def _emit_result(
    module: AnsibleModule,
    path: str,
    desired: dict[str, Any],
    changed: bool,
    existed_before: bool,
    data: dict[str, Any],
) -> None:
    """Emit the module operation log and Ansible result."""
    transition = _state_transition(
        changed=changed,
        existed_before=existed_before,
        state=module.params["state"],
    )
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


def main() -> None:
    """Run the Ansible module."""
    module = AnsibleModule(
        argument_spec=_build_argument_spec(),
        supports_check_mode=True,
    )

    path = _resolve_hook_path(module)
    extra = module.params.get("extra") or {}
    conflicting_extra_keys = sorted(MANAGED_HOOK_FIELDS & set(extra))
    if conflicting_extra_keys:
        module.fail_json(
            msg=(
                "invalid extra keys for deepseek_tui_hook: "
                + ", ".join(conflicting_extra_keys)
            )
        )
    hook_params = HookParams(
        event=module.params["event"],
        command=module.params["command"],
        name=module.params.get("name"),
        condition=module.params.get("condition"),
        timeout_secs=module.params.get("timeout_secs"),
        background=module.params.get("background"),
        continue_on_error=module.params.get("continue_on_error"),
        extra=extra,
    )
    desired = build_hook_definition(hook_params)
    changed, data, existed_before = _apply_hook_changes(module, path, desired)
    _emit_result(module, path, desired, changed, existed_before, data)


if __name__ == "__main__":
    main()
