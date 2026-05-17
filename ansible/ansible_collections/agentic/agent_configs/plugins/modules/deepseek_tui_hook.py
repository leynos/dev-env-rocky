#!/usr/bin/python
"""Manage DeepSeek-TUI lifecycle hooks in config.toml.

This module performs read-modify-write updates on ``config.toml``. Serialise
parallel writes externally, for example by running the play with ``serial: 1``
when several hosts or tasks can target the same file.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    _state_transition,
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

MANAGED_KEYS = {
    "event",
    "command",
    "name",
    "condition",
    "timeout_secs",
    "background",
    "continue_on_error",
}
MANAGED_HOOK_FIELDS = MANAGED_KEYS


@dataclass(frozen=True, slots=True)
class HookParams:
    """Value object encapsulating the fields of a single DeepSeek-TUI hook."""

    event: str
    command: str
    name: str | None = None
    condition: dict[str, Any] | None = None
    timeout_secs: int | None = None
    background: bool | None = None
    continue_on_error: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def build_hook_definition(params: HookParams) -> dict[str, Any]:
    """Build a DeepSeek-TUI hook definition from domain parameters."""
    desired: dict[str, Any] = {
        "event": params.event,
        "command": params.command,
        "name": params.name,
        "condition": params.condition,
        "timeout_secs": params.timeout_secs,
        "background": params.background,
        "continue_on_error": params.continue_on_error,
    }
    desired.update(
        {key: value for key, value in params.extra.items() if key not in MANAGED_KEYS}
    )
    return clean_dict(desired)


def hook_identity_matches(existing: dict[str, Any], desired: dict[str, Any]) -> bool:
    """Return whether two hook entries represent the same managed hook."""
    if existing.get("event") != desired.get("event"):
        return False
    if desired.get("name") is not None or existing.get("name") is not None:
        return existing.get("name") == desired.get("name")
    return existing.get("command") == desired.get("command")


def hook_without_managed_identity(hook: object, desired: dict[str, Any]) -> bool:
    """Return whether an existing hook should be retained."""
    return not (isinstance(hook, dict) and hook_identity_matches(hook, desired))


def apply_global_hook_options(
    hooks_root: dict[str, Any],
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


def ensure_hook_toml_shape(path: str, data: object) -> dict[str, Any]:
    """Return a mutable TOML root object or raise a contextual validation error."""
    if not isinstance(data, dict):
        raise ValueError(f"Expected TOML root object path={path!r}")
    return data


def ensure_hooks_root(path: str, data: dict[str, Any]) -> dict[str, Any]:
    """Return the mutable DeepSeek-TUI hooks table."""
    hooks_root = data.setdefault("hooks", {})
    if not isinstance(hooks_root, dict):
        raise ValueError(f"Expected 'hooks' to be a table path={path!r}")
    return hooks_root


def ensure_hook_entries(path: str, hooks_root: dict[str, Any]) -> list[object]:
    """Return the mutable hook entry list."""
    hook_entries = hooks_root.setdefault("hooks", [])
    if not isinstance(hook_entries, list):
        raise ValueError(f"Expected 'hooks.hooks' to be a list path={path!r}")
    return hook_entries


def _apply_present_hook(
    hook_entries: list[object],
    desired_hook: dict[str, Any],
) -> bool:
    """Upsert *desired_hook* into *hook_entries*; return True if a change was made."""
    for index, hook in enumerate(hook_entries):
        if isinstance(hook, dict) and hook_identity_matches(hook, desired_hook):
            if hook != desired_hook:
                hook_entries[index] = desired_hook
                return True
            return False
    hook_entries.append(desired_hook)
    return True


def _apply_absent_hook(
    hooks_root: dict[str, Any],
    data: dict[str, Any],
    hook_entries: list[object],
    desired_hook: dict[str, Any],
) -> bool:
    """Remove any hook matching *desired_hook*; prune empty containers.

    Returns True if the hook list was modified.
    """
    retained = [
        hook
        for hook in hook_entries
        if hook_without_managed_identity(hook, desired_hook)
    ]
    if retained == hook_entries:
        return False
    hooks_root["hooks"] = retained
    if not hooks_root.get("hooks"):
        hooks_root.pop("hooks", None)
    if not hooks_root:
        data.pop("hooks", None)
    return True


def _persist_hook_changes(
    module: AnsibleModule,
    path: str,
    data: dict[str, Any],
    changed: bool,
    removed_legacy_block: bool,
    existed_before: bool,
) -> tuple[bool, dict[str, Any], bool]:
    """Write TOML to disk (unless check mode) when pending changes exist."""
    if changed or removed_legacy_block:
        if module.check_mode:
            return True, data, existed_before
        if removed_legacy_block:
            changed = True
        write_toml_if_changed(module, path, data)
    return changed, data, existed_before


def manage_hook_toml(
    module: AnsibleModule,
    path: str,
    desired_hook: dict[str, Any],
    state: str,
) -> tuple[bool, dict[str, Any], bool]:
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
        changed |= _apply_present_hook(hook_entries, desired_hook)
    else:
        changed |= _apply_absent_hook(hooks_root, data, hook_entries, desired_hook)

    return _persist_hook_changes(
        module, path, data, changed, removed_legacy_block, existed_before
    )


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
