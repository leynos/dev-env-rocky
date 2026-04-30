# -*- coding: utf-8 -*-
"""Shared helpers for agent configuration Ansible modules."""

from __future__ import annotations

import copy
import json
import math
import os
import re
import shutil
import tempfile
from datetime import date, datetime, time
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:  # Python 3.11+
    import tomllib  # type: ignore
except Exception:  # pragma: no cover - older Python
    try:
        import tomli as tomllib  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        tomllib = None  # type: ignore

TRUE_STRINGS = {"1", "true", "yes", "on"}


def expand_path(path: str) -> str:
    """Return an absolute path with a leading user home marker expanded."""
    return os.path.abspath(os.path.expanduser(path))


def deep_copy(value: Any) -> Any:
    """Return a defensive deep copy of a JSON-like value."""
    return copy.deepcopy(value)


def ensure_unicode_text(value: str) -> str:
    """Normalize text to Unix newlines before rendering managed files."""
    return value.replace("\r\n", "\n").replace("\r", "\n")


class ChangeSet:
    """Collect path-level changes for multi-file module operations."""

    def __init__(self) -> None:
        """Create an empty change accumulator."""
        self.changed = False
        self.paths: List[str] = []
        self.details: Dict[str, Any] = {}

    def note(self, changed: bool, path: Optional[str] = None, **details: Any) -> None:
        """Record a changed path and optional diagnostic details."""
        if changed:
            self.changed = True
            if path and path not in self.paths:
                self.paths.append(path)
        if details:
            self.details.update(details)


def coerce_bool(value: Any, default: bool = False) -> bool:
    """Coerce common Ansible-style truthy values into a boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in TRUE_STRINGS
    return bool(value)


def ensure_directory(path: str) -> bool:
    """Create a directory when it is missing and report whether it changed."""
    path = expand_path(path)
    if os.path.isdir(path):
        return False
    os.makedirs(path, exist_ok=True)
    return True


def read_text(path: str) -> Optional[str]:
    """Read UTF-8 text from a path, returning ``None`` when it is absent."""
    path = expand_path(path)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def atomic_write_text(path: str, content: str) -> None:
    """Atomically replace a UTF-8 text file with the supplied content.

    Raises:
        OSError: If the parent directory, temporary file, or final rename cannot
            be created.
    """
    path = expand_path(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".ansible-agent-config-", dir=parent or None)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def log_operation(module, operation: str, **fields: Any) -> None:
    """Emit a structured module log message when Ansible exposes logging."""
    logger = getattr(module, "log", None)
    if logger is None:
        return
    payload = {"operation": operation, **fields}
    logger(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def fail_with_io_error(module, operation: str, path: str, exc: OSError) -> None:
    """Fail an Ansible module with a consistent I/O error message."""
    log_operation(module, operation + "_failed", path=expand_path(path), error=str(exc))
    module.fail_json(msg="%s failed for %s: %s" % (operation, expand_path(path), exc))


def write_text_if_changed(module, path: str, content: str) -> bool:
    """Write text only when content differs, respecting Ansible check mode."""
    path = expand_path(path)
    try:
        current = read_text(path)
    except OSError as exc:
        fail_with_io_error(module, "read_text", path, exc)
    if current == content:
        log_operation(module, "write_text_if_changed", path=path, changed=False)
        return False
    if module.check_mode:
        log_operation(
            module, "write_text_if_changed", path=path, changed=True, check_mode=True
        )
        return True
    try:
        atomic_write_text(path, content)
    except OSError as exc:
        fail_with_io_error(module, "write_text", path, exc)
    log_operation(module, "write_text_if_changed", path=path, changed=True)
    return True


def remove_path(module, path: str, recursive: bool = False) -> bool:
    """Remove a file or directory, respecting Ansible check mode."""
    path = expand_path(path)
    if not os.path.exists(path):
        log_operation(module, "remove_path", path=path, changed=False)
        return False
    if module.check_mode:
        log_operation(module, "remove_path", path=path, changed=True, check_mode=True)
        return True
    try:
        if recursive and os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except OSError as exc:
        fail_with_io_error(module, "remove_path", path, exc)
    log_operation(module, "remove_path", path=path, changed=True, recursive=recursive)
    return True


def load_json_file(path: str, default: Optional[Any] = None) -> Any:
    """Load JSON from a file, returning a copied default when absent."""
    path = expand_path(path)
    if default is None:
        default = {}
    if not os.path.exists(path):
        return deep_copy(default)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(data: Any) -> str:
    """Render JSON using the repository's stable formatting convention."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json_if_changed(module, path: str, data: Any) -> bool:
    """Render JSON and write it when the target content differs."""
    return write_text_if_changed(module, path, dump_json(data))


def load_toml_file(module, path: str, default: Optional[Any] = None) -> Any:
    """Load TOML from a file, returning a copied default when absent."""
    path = expand_path(path)
    if default is None:
        default = {}
    if not os.path.exists(path):
        return deep_copy(default)
    if tomllib is None:
        module.fail_json(
            msg="Reading TOML requires Python 3.11+ or the tomli package on the target host"
        )
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except OSError as exc:
        fail_with_io_error(module, "read_toml", path, exc)


def _toml_key(key: str) -> str:
    """Render a TOML key, quoting keys that need escaping."""
    if re.match(r"^[A-Za-z0-9_-]+$", key):
        return key
    return json.dumps(key, ensure_ascii=False)


def _toml_scalar(value: Any) -> str:
    """Render a supported scalar value as TOML syntax."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            raise TypeError("TOML does not support NaN or infinity")
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    raise TypeError("Unsupported TOML scalar type: %s" % type(value).__name__)


def _is_list_of_dicts(value: Any) -> bool:
    """Return whether a value should be rendered as an array of tables."""
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, dict) for item in value)
    )


def _toml_value(value: Any) -> str:
    """Render a scalar or scalar list as TOML syntax."""
    if isinstance(value, list):
        if _is_list_of_dicts(value):
            raise TypeError("List of dicts must be rendered as an array of tables")
        return "[{}]".format(", ".join(_toml_scalar(item) for item in value))
    return _toml_scalar(value)


def _toml_render_table(
    lines: List[str], prefix: List[str], mapping: Dict[str, Any]
) -> None:
    """Append TOML table lines for a nested mapping."""
    scalar_items: List[Tuple[str, Any]] = []
    table_items: List[Tuple[str, Any]] = []
    array_table_items: List[Tuple[str, List[Dict[str, Any]]]] = []

    for key, value in mapping.items():
        if isinstance(value, dict):
            table_items.append((key, value))
        elif _is_list_of_dicts(value):
            array_table_items.append((key, value))
        else:
            scalar_items.append((key, value))

    if prefix:
        lines.append("[{}]".format(".".join(_toml_key(item) for item in prefix)))
    for key, value in scalar_items:
        lines.append("{} = {}".format(_toml_key(key), _toml_value(value)))

    if scalar_items and (table_items or array_table_items):
        lines.append("")

    for index, (key, value) in enumerate(table_items):
        _toml_render_table(lines, prefix + [key], value)
        if index != len(table_items) - 1 or array_table_items:
            lines.append("")

    for outer_index, (key, rows) in enumerate(array_table_items):
        for inner_index, row in enumerate(rows):
            lines.append(
                "[[{}]]".format(".".join(_toml_key(item) for item in prefix + [key]))
            )
            scalar_subitems: List[Tuple[str, Any]] = []
            nested_table_items: List[Tuple[str, Any]] = []
            nested_array_table_items: List[Tuple[str, List[Dict[str, Any]]]] = []
            for subkey, subvalue in row.items():
                if isinstance(subvalue, dict):
                    nested_table_items.append((subkey, subvalue))
                elif _is_list_of_dicts(subvalue):
                    nested_array_table_items.append((subkey, subvalue))
                else:
                    scalar_subitems.append((subkey, subvalue))
            for subkey, subvalue in scalar_subitems:
                lines.append("{} = {}".format(_toml_key(subkey), _toml_value(subvalue)))
            if scalar_subitems and (nested_table_items or nested_array_table_items):
                lines.append("")
            for nested_index, (subkey, subvalue) in enumerate(nested_table_items):
                _toml_render_table(lines, prefix + [key, subkey], subvalue)
                if (
                    nested_index != len(nested_table_items) - 1
                    or nested_array_table_items
                ):
                    lines.append("")
            for nested_arr_index, (subkey, subrows) in enumerate(
                nested_array_table_items
            ):
                for subrow_index, subrow in enumerate(subrows):
                    lines.append(
                        "[[{}]]".format(
                            ".".join(_toml_key(item) for item in prefix + [key, subkey])
                        )
                    )
                    for item_key, item_value in subrow.items():
                        if isinstance(item_value, (dict, list)) and _is_list_of_dicts(
                            item_value
                        ):
                            raise TypeError(
                                "Nested arrays of tables beyond two levels are not supported"
                            )
                        if isinstance(item_value, dict):
                            raise TypeError(
                                "Nested dicts inside array-of-table items are not supported"
                            )
                        lines.append(
                            "{} = {}".format(
                                _toml_key(item_key), _toml_value(item_value)
                            )
                        )
                    if subrow_index != len(subrows) - 1:
                        lines.append("")
                if nested_arr_index != len(nested_array_table_items) - 1:
                    lines.append("")
            if inner_index != len(rows) - 1:
                lines.append("")
        if outer_index != len(array_table_items) - 1:
            lines.append("")


def dump_toml(data: Dict[str, Any]) -> str:
    """Render a nested mapping as deterministic TOML."""
    if not isinstance(data, dict):
        raise TypeError("TOML root must be a mapping")
    lines: List[str] = []
    _toml_render_table(lines, [], data)
    rendered = "\n".join(lines).rstrip() + "\n"
    return rendered


def write_toml_if_changed(module, path: str, data: Dict[str, Any]) -> bool:
    """Render TOML and write it when the target content differs."""
    return write_text_if_changed(module, path, dump_toml(data))


def slugify(name: str) -> str:
    """Convert a human-readable resource name into a stable file slug."""
    text = ensure_unicode_text(name).strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-._")
    return text or "resource"


def yaml_scalar(value: Any) -> str:
    """Render a scalar for the limited YAML front matter writer."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def yaml_dump(mapping: Dict[str, Any], indent: int = 0) -> str:
    """Render a simple YAML mapping for generated Markdown front matter."""
    lines: List[str] = []
    pad = " " * indent
    for key, value in mapping.items():
        if isinstance(value, dict):
            if not value:
                lines.append(f"{pad}{key}: {{}}")
            else:
                lines.append(f"{pad}{key}:")
                lines.append(yaml_dump(value, indent + 2))
        elif isinstance(value, list):
            if not value:
                lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{pad}  -")
                        lines.append(yaml_dump(item, indent + 4))
                    else:
                        lines.append(f"{pad}  - {yaml_scalar(item)}")
        else:
            lines.append(f"{pad}{key}: {yaml_scalar(value)}")
    return "\n".join(lines)


def render_markdown(frontmatter: Dict[str, Any], body: str) -> str:
    """Render Markdown with YAML front matter and normalized body text."""
    normal_body = ensure_unicode_text(body).rstrip()
    fm = yaml_dump(frontmatter)
    if normal_body:
        return "---\n{}\n---\n\n{}\n".format(fm, normal_body)
    return "---\n{}\n---\n".format(fm)


def normalize_mapping_order(
    mapping: Dict[str, Any], preferred_keys: Iterable[str]
) -> Dict[str, Any]:
    """Return a mapping ordered by preferred keys, then sorted remaining keys."""
    ordered: Dict[str, Any] = {}
    preferred = list(preferred_keys)
    for key in preferred:
        if key in mapping and mapping[key] is not None:
            ordered[key] = mapping[key]
    for key in sorted(mapping.keys()):
        if key not in ordered and mapping[key] is not None:
            ordered[key] = mapping[key]
    return ordered


def merge_dicts(
    base: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Merge two optional dictionaries without mutating either input."""
    result: Dict[str, Any] = {}
    if base:
        result.update(base)
    if extra:
        result.update(extra)
    return result


def resolve_scoped_config_path(
    path: Optional[str],
    scope: str,
    project_dir: Optional[str],
    user_path: str,
    project_relative_path: str,
    local_relative_path: Optional[str] = None,
) -> str:
    """Resolve user, project, or local configuration paths."""
    if path:
        return expand_path(path)
    if scope == "user":
        return expand_path(user_path)
    if not project_dir:
        raise ValueError("project_dir is required when scope is not 'user'")
    project_dir = expand_path(project_dir)
    if scope == "project":
        return os.path.join(project_dir, project_relative_path)
    if scope == "local":
        if local_relative_path is None:
            raise ValueError("This resource type does not support local scope")
        return os.path.join(project_dir, local_relative_path)
    raise ValueError("Unsupported scope: %s" % scope)


def resolve_relative_config_file(subagent_path: str, config_path: str) -> str:
    """Resolve a subagent file path relative to its Codex config directory.

    Returns an absolute path when the subagent file is outside the config
    directory. Raises no exception for paths on different drives or roots.
    """
    expanded_subagent_path = expand_path(subagent_path)
    expanded_config_dir = os.path.dirname(expand_path(config_path))
    try:
        common_path = os.path.commonpath([expanded_subagent_path, expanded_config_dir])
    except ValueError:
        return expanded_subagent_path
    if common_path != expanded_config_dir:
        return expanded_subagent_path
    return os.path.relpath(expanded_subagent_path, expanded_config_dir)


def manage_named_json_entry(
    module,
    path: str,
    root_key: str,
    name: str,
    desired: Optional[Dict[str, Any]],
    state: str,
) -> Tuple[bool, Dict[str, Any]]:
    """Create, update, or remove a named object inside a JSON root object."""
    path = expand_path(path)
    data = load_json_file(path, default={})
    if not isinstance(data, dict):
        module.fail_json(msg="Expected JSON object in %s" % path)
    root = data.setdefault(root_key, {})
    if not isinstance(root, dict):
        module.fail_json(
            msg="Expected '%s' to be a JSON object in %s" % (root_key, path)
        )

    changed = False
    if state == "present":
        if root.get(name) != desired:
            root[name] = desired
            changed = True
    else:
        if name in root:
            del root[name]
            changed = True
        if not root:
            data.pop(root_key, None)

    if changed:
        if module.check_mode:
            log_operation(
                module,
                "manage_named_json_entry",
                path=path,
                root_key=root_key,
                name=name,
                state=state,
                changed=True,
                check_mode=True,
            )
            return True, data
        write_json_if_changed(module, path, data)
    log_operation(
        module,
        "manage_named_json_entry",
        path=path,
        root_key=root_key,
        name=name,
        state=state,
        changed=changed,
    )
    return changed, data


def manage_named_toml_entry(
    module,
    path: str,
    root_key: str,
    name: str,
    desired: Optional[Dict[str, Any]],
    state: str,
) -> Tuple[bool, Dict[str, Any]]:
    """Create, update, or remove a named table inside a TOML root table."""
    path = expand_path(path)
    data = load_toml_file(module, path, default={})
    if not isinstance(data, dict):
        module.fail_json(msg="Expected TOML root object in %s" % path)
    root = data.setdefault(root_key, {})
    if not isinstance(root, dict):
        module.fail_json(msg="Expected '%s' to be a table in %s" % (root_key, path))

    changed = False
    if state == "present":
        if root.get(name) != desired:
            root[name] = desired
            changed = True
    else:
        if name in root:
            del root[name]
            changed = True
        if not root:
            data.pop(root_key, None)

    if changed:
        if module.check_mode:
            log_operation(
                module,
                "manage_named_toml_entry",
                path=path,
                root_key=root_key,
                name=name,
                state=state,
                changed=True,
                check_mode=True,
            )
            return True, data
        write_toml_if_changed(module, path, data)
    log_operation(
        module,
        "manage_named_toml_entry",
        path=path,
        root_key=root_key,
        name=name,
        state=state,
        changed=changed,
    )
    return changed, data


def _hook_group_matches(group: Dict[str, Any], matcher: Optional[str]) -> bool:
    """Return whether a hook group matches a requested matcher."""
    group_matcher = group.get("matcher")
    if matcher in (None, ""):
        return group_matcher in (None, "")
    return group_matcher == matcher


def _hook_identity_matches(
    existing: Dict[str, Any], desired: Dict[str, Any], identity_keys: Iterable[str]
) -> bool:
    """Return whether two hook definitions share the same identity fields."""
    for key in identity_keys:
        if existing.get(key) != desired.get(key):
            return False
    return True


def _find_hook_group_index(groups: List[Any], matcher: Optional[str]) -> Optional[int]:
    """Find the hook group index for a matcher."""
    for idx, group in enumerate(groups):
        if isinstance(group, dict) and _hook_group_matches(group, matcher):
            return idx
    return None


def _get_hook_list(
    module,
    group: Dict[str, Any],
    event: str,
    path: str,
    *,
    create: bool,
) -> List[Any]:
    """Get the hook list for a hook group."""
    hook_list = group.setdefault("hooks", []) if create else group.get("hooks", [])
    if not isinstance(hook_list, list):
        module.fail_json(msg="Expected hooks list under event %s in %s" % (event, path))
    return hook_list


def _ensure_hook_group(
    groups: List[Any],
    matcher: Optional[str],
    group_index: Optional[int],
) -> Tuple[bool, Dict[str, Any]]:
    """Ensure a hook group exists for a matcher."""
    if group_index is not None:
        return False, groups[group_index]

    group: Dict[str, Any] = {"hooks": []}
    if matcher not in (None, ""):
        group["matcher"] = matcher
    groups.append(group)
    return True, group


def _find_hook_index(
    hook_list: List[Any],
    desired_hook: Dict[str, Any],
    identity_keys: Iterable[str],
) -> Optional[int]:
    """Find the hook index for the desired hook identity."""
    for idx, hook in enumerate(hook_list):
        if isinstance(hook, dict) and _hook_identity_matches(
            hook,
            desired_hook,
            identity_keys,
        ):
            return idx
    return None


def _upsert_hook_json_group(
    module,
    groups: List[Any],
    matcher: Optional[str],
    group_index: Optional[int],
    desired_hook: Dict[str, Any],
    identity_keys: Iterable[str],
    event: str,
    path: str,
) -> bool:
    """Upsert the desired hook into a hook group."""
    changed, group = _ensure_hook_group(groups, matcher, group_index)
    hook_list = _get_hook_list(module, group, event, path, create=True)
    existing_index = _find_hook_index(hook_list, desired_hook, identity_keys)
    if existing_index is None:
        hook_list.append(desired_hook)
        return True
    if hook_list[existing_index] != desired_hook:
        hook_list[existing_index] = desired_hook
        return True
    return changed


def _remove_hook_json_group(
    module,
    groups: List[Any],
    group_index: Optional[int],
    desired_hook: Dict[str, Any],
    identity_keys: Iterable[str],
    event: str,
    path: str,
) -> bool:
    """Remove the desired hook from a hook group."""
    if group_index is None:
        return False

    group = groups[group_index]
    hook_list = _get_hook_list(module, group, event, path, create=False)
    retained = [
        hook
        for hook in hook_list
        if not (
            isinstance(hook, dict)
            and _hook_identity_matches(hook, desired_hook, identity_keys)
        )
    ]
    if retained == hook_list:
        return False

    group["hooks"] = retained
    if not retained:
        groups.pop(group_index)
    return True


def _prune_empty_hook_roots(
    data: Dict[str, Any],
    hooks_root: Dict[str, Any],
    event: str,
    groups: List[Any],
) -> None:
    """Prune empty hook roots from the configuration data."""
    if not groups:
        hooks_root.pop(event, None)
    if not hooks_root:
        data.pop("hooks", None)


def manage_hook_json(
    module,
    path: str,
    event: str,
    matcher: Optional[str],
    desired_hook: Dict[str, Any],
    state: str,
    identity_keys: Iterable[str],
) -> Tuple[bool, Dict[str, Any]]:
    """Create, update, or remove a command hook in a JSON hook config file."""
    path = expand_path(path)
    data = load_json_file(path, default={})
    if not isinstance(data, dict):
        module.fail_json(msg="Expected JSON object in %s" % path)
    hooks_root = data.setdefault("hooks", {})
    if not isinstance(hooks_root, dict):
        module.fail_json(msg="Expected 'hooks' to be a JSON object in %s" % path)
    groups = hooks_root.setdefault(event, [])
    if not isinstance(groups, list):
        module.fail_json(msg="Expected hooks['%s'] to be a list in %s" % (event, path))

    group_index = _find_hook_group_index(groups, matcher)
    if state == "present":
        changed = _upsert_hook_json_group(
            module,
            groups,
            matcher,
            group_index,
            desired_hook,
            identity_keys,
            event,
            path,
        )
    else:
        changed = _remove_hook_json_group(
            module,
            groups,
            group_index,
            desired_hook,
            identity_keys,
            event,
            path,
        )
        _prune_empty_hook_roots(data, hooks_root, event, groups)

    if changed:
        if module.check_mode:
            log_operation(
                module,
                "manage_hook_json",
                path=path,
                event=event,
                state=state,
                changed=True,
                check_mode=True,
            )
            return True, data
        write_json_if_changed(module, path, data)
    log_operation(
        module,
        "manage_hook_json",
        path=path,
        event=event,
        state=state,
        changed=changed,
    )
    return changed, data


def manage_markdown_file(
    module, path: str, frontmatter: Dict[str, Any], body: str, state: str
) -> bool:
    """Manage a single Markdown file with YAML front matter."""
    path = expand_path(path)
    if state == "absent":
        return remove_path(module, path, recursive=False)
    content = render_markdown(frontmatter, body)
    return write_text_if_changed(module, path, content)


def manage_directory_markdown_resource(
    module,
    directory: str,
    primary_filename: str,
    frontmatter: Dict[str, Any],
    body: str,
    state: str,
    extra_files: Optional[Dict[str, str]] = None,
) -> ChangeSet:
    """Manage a directory-backed Markdown resource and optional extra files."""
    directory = expand_path(directory)
    changes = ChangeSet()
    if state == "absent":
        changes.note(remove_path(module, directory, recursive=True), path=directory)
        return changes

    if not os.path.isdir(directory):
        if module.check_mode:
            changes.note(True, path=directory)
        else:
            ensure_directory(directory)
            changes.note(True, path=directory)

    primary_path = os.path.join(directory, primary_filename)
    changed = manage_markdown_file(
        module, primary_path, frontmatter, body, state="present"
    )
    changes.note(changed, path=primary_path)

    extra_files = extra_files or {}
    for relative_path, content in sorted(extra_files.items()):
        target_path = os.path.join(directory, relative_path)
        changed = write_text_if_changed(
            module, target_path, ensure_unicode_text(content)
        )
        changes.note(changed, path=target_path)

    return changes


def maybe_validate_executable(module, executable: str, validate: bool) -> None:
    """Validate that an agent executable path exists and is executable."""
    if not validate:
        return
    if not executable:
        module.fail_json(msg="agent_executable is required")
    resolved = expand_path(executable)
    if not os.path.exists(resolved):
        module.fail_json(msg="Executable not found: %s" % resolved)
    if os.name != "nt" and not os.access(resolved, os.X_OK):
        module.fail_json(msg="Path is not executable: %s" % resolved)


def clean_dict(value: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dictionary without keys whose values are ``None``."""
    return {key: item for key, item in value.items() if item is not None}


def ensure_parent_directory_for_file(module, path: str) -> bool:
    """Ensure the parent directory for a file path exists."""
    parent = os.path.dirname(expand_path(path))
    if not parent:
        return False
    if os.path.isdir(parent):
        return False
    if module.check_mode:
        return True
    os.makedirs(parent, exist_ok=True)
    return True
