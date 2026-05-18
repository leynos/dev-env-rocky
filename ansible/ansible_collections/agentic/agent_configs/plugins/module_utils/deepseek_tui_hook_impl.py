"""Implementation helpers for the DeepSeek-TUI hook module."""

from dataclasses import dataclass, field
from typing import Any

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    expand_path,
    load_toml_file,
    write_toml_if_changed,
)

GLOBAL_HOOK_OPTION_KEYS = frozenset({"enabled", "default_timeout_secs", "working_dir"})

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


@dataclass(frozen=True, slots=True)
class _HookPreState:
    """Snapshot of hook container existence captured before any mutation."""

    had_hooks_table: bool
    had_hook_entries: bool


def _had_hook_entries_before(data: dict[str, Any]) -> bool:
    """Return whether the TOML data already contained a hooks.hooks list before mutation."""
    hooks = data.get("hooks")
    return isinstance(hooks, dict) and "hooks" in hooks


def _hooks_list_is_missing_or_empty(hooks_root: object) -> bool:
    """Return True when hooks.hooks is absent or an empty list."""
    return isinstance(hooks_root, dict) and hooks_root.get("hooks") in (None, [])


def _hooks_root_has_global_options(hooks_root: object) -> bool:
    """Return True when hooks_root contains explicit global hook options."""
    return isinstance(hooks_root, dict) and bool(
        GLOBAL_HOOK_OPTION_KEYS & hooks_root.keys()
    )


def _cleanup_absent_noop(
    state: str,
    changed: bool,
    pre_state: _HookPreState,
    data: dict[str, Any],
) -> None:
    """Prune TOML containers created by setdefault when an absent hook was already missing."""
    del changed
    if state != "absent":
        return
    hooks_root = data.get("hooks")
    if not pre_state.had_hook_entries and _hooks_list_is_missing_or_empty(hooks_root):
        hooks_root.pop("hooks", None)
    if not pre_state.had_hooks_table and not _hooks_root_has_global_options(hooks_root):
        data.pop("hooks", None)


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
    pre_state = _HookPreState(
        had_hooks_table="hooks" in data,
        had_hook_entries=_had_hook_entries_before(data),
    )
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

    _cleanup_absent_noop(state, changed, pre_state, data)

    return _persist_hook_changes(
        module, path, data, changed, removed_legacy_block, existed_before
    )
