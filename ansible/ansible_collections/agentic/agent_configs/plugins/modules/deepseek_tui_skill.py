#!/usr/bin/python
"""Manage DeepSeek-TUI skill directories.

This module performs read-modify-write updates across a skill directory.
Serialize parallel writes externally, for example by running the play with
``serial: 1`` when several hosts or tasks can target the same directory.
"""

from pathlib import Path
from typing import Any

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    _state_transition,
    expand_path,
    log_operation,
    manage_directory_markdown_resource,
    merge_dicts,
    normalize_mapping_order,
    resolve_scoped_config_path,
    slugify,
)

DOCUMENTATION = r"""
---
module: deepseek_tui_skill
short_description: Manage DeepSeek-TUI skills
version_added: "1.0.0"
description:
  - Manage DeepSeek-TUI skill directories containing C(SKILL.md) and optional support files.
options:
  name:
    description:
      - Skill display name.
    type: str
    required: true
  slug:
    description:
      - Directory name for the skill.
      - Defaults to a slug derived from C(name).
    type: str
  state:
    description:
      - Whether the managed resource should exist.
    type: str
    choices: [present, absent]
    default: present
  scope:
    description:
      - Skill location scope.
      - C(project) writes to C(.agents/skills/<slug>) because DeepSeek-TUI prefers that workspace path when present.
    type: str
    choices: [user, project]
    default: user
  project_dir:
    description:
      - Project root used when C(scope=project).
    type: path
  path:
    description:
      - Exact skill directory to manage.
      - Overrides C(scope), C(project_dir), and C(slug).
    type: path
  description:
    description:
      - Skill description used in front matter.
      - Required when C(state=present).
    type: str
  body:
    description:
      - Markdown body for C(SKILL.md).
    type: str
    default: ''
  metadata:
    description:
      - Additional front matter keys.
    type: dict
    default: {}
  extra_files:
    description:
      - Optional extra files written relative to the skill directory.
      - Keys are relative paths and values are file contents.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Install a user DeepSeek-TUI skill
  agentic.agent_configs.deepseek_tui_skill:
    name: Release helper
    description: Run the release flow and verify artefacts.
    body: |
      Follow docs/release.md and summarise any blockers.

- name: Install a project DeepSeek-TUI skill
  agentic.agent_configs.deepseek_tui_skill:
    name: Repository reviewer
    scope: project
    project_dir: /srv/my-repo
    description: Review this repository's changes.
    body: |
      Check the local AGENTS.md before reviewing.
"""

RETURN = r"""
directory:
  description: Managed skill directory.
  returned: always
  type: str
paths:
  description: Changed paths.
  returned: when changed
  type: list
  elements: str
"""


def _validate_present_skill_params(params: dict[str, Any]) -> None:
    """Validate skill parameters that are required only for present resources."""
    if params["state"] == "present" and not params.get("description"):
        msg = (
            "description is required when state=present "
            f"name={params.get('name')!r} scope={params.get('scope')!r}"
        )
        raise ValueError(msg)


def _build_frontmatter(
    *,
    name: str,
    description: str | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Build DeepSeek-TUI skill front matter from domain parameters."""
    base: dict[str, Any] = {
        "name": name,
        "description": description,
    }
    filtered_metadata = {
        key: value
        for key, value in metadata.items()
        if key not in {"name", "description"}
    }
    return normalize_mapping_order(
        merge_dicts(base, filtered_metadata),
        ["name", "description"],
    )


def _resolve_directory(
    *,
    path: str | None,
    scope: str,
    project_dir: str | None,
    slug: str,
) -> str:
    """Resolve the managed DeepSeek-TUI skill directory."""
    if path:
        return path
    return resolve_scoped_config_path(
        path=None,
        scope=scope,
        project_dir=project_dir,
        user_path=str(Path("~/.deepseek/skills") / slug),
        project_relative_path=str(Path(".agents/skills") / slug),
    )


def _build_argument_spec() -> dict[str, Any]:
    """Return the argument spec for the deepseek_tui_skill module."""
    return {
        "name": {"type": "str", "required": True},
        "slug": {"type": "str"},
        "state": {
            "type": "str",
            "choices": ["present", "absent"],
            "default": "present",
        },
        "scope": {"type": "str", "choices": ["user", "project"], "default": "user"},
        "project_dir": {"type": "path"},
        "path": {"type": "path"},
        "description": {"type": "str"},
        "body": {"type": "str", "default": ""},
        "metadata": {"type": "dict", "default": {}},
        "extra_files": {"type": "dict", "default": {}},
    }


def _resolve_skill_directory(module: AnsibleModule, slug: str) -> str:
    """Validate params and resolve the skill directory path, failing the module on error."""
    try:
        _validate_present_skill_params(module.params)
        return _resolve_directory(
            path=module.params.get("path"),
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            slug=slug,
        )
    except ValueError as exc:
        module.fail_json(
            msg=(
                "failed to resolve DeepSeek-TUI skill directory "
                f"name={module.params.get('name')!r} "
                f"scope={module.params.get('scope')!r} "
                f"state={module.params.get('state')!r}: {exc}"
            )
        )


def _emit_skill_result(
    module: AnsibleModule,
    directory: str,
    slug: str,
    changes: object,
    existed_before: bool,
) -> None:
    """Log the operation and exit the module with the computed result."""
    transition = _state_transition(
        changed=changes.changed,
        existed_before=existed_before,
        state=module.params["state"],
    )
    log_operation(
        module,
        "deepseek_tui_skill",
        action=transition,
        path=directory,
        name=module.params["name"],
        slug=slug,
        scope=module.params["scope"],
        state=module.params["state"],
        changed=changes.changed,
        changed_paths=changes.paths,
    )
    module.exit_json(
        changed=changes.changed,
        directory=directory,
        paths=changes.paths,
        scope=module.params["scope"],
        slug=slug,
        name=module.params["name"],
        state_transition=transition,
    )


def main() -> None:
    """Run the Ansible module."""
    module = AnsibleModule(
        argument_spec=_build_argument_spec(),
        required_if=[["state", "present", ["description"]]],
        supports_check_mode=True,
    )

    slug = module.params.get("slug") or slugify(module.params["name"])
    directory = _resolve_skill_directory(module, slug)
    existed_before = Path(expand_path(directory)).is_dir()
    changes = manage_directory_markdown_resource(
        module=module,
        directory=directory,
        primary_filename="SKILL.md",
        frontmatter=_build_frontmatter(
            name=module.params["name"],
            description=module.params.get("description"),
            metadata=module.params.get("metadata") or {},
        ),
        body=module.params["body"],
        state=module.params["state"],
        extra_files=module.params.get("extra_files") or {},
    )
    _emit_skill_result(module, directory, slug, changes, existed_before)


if __name__ == "__main__":
    main()
