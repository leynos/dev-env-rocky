#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Manage DeepSeek-TUI skill directories."""

from __future__ import annotations

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
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


def build_frontmatter(module: AnsibleModule) -> dict:
    """Build DeepSeek-TUI skill front matter from module parameters."""
    params = module.params
    if params["state"] == "present" and not params.get("description"):
        module.fail_json(msg="description is required when state=present")
    base = {
        "name": params["name"],
        "description": params.get("description"),
    }
    return normalize_mapping_order(
        merge_dicts(base, params.get("metadata") or {}),
        ["name", "description"],
    )


def resolve_directory(module: AnsibleModule) -> str:
    """Resolve the managed DeepSeek-TUI skill directory."""
    if module.params.get("path"):
        return module.params["path"]
    slug = module.params.get("slug") or slugify(module.params["name"])
    try:
        return resolve_scoped_config_path(
            path=None,
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path=os.path.join("~/.deepseek/skills", slug),
            project_relative_path=os.path.join(".agents/skills", slug),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))


def main() -> None:
    """Run the Ansible module."""
    module = AnsibleModule(
        argument_spec={
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
        },
        supports_check_mode=True,
    )

    directory = resolve_directory(module)
    changes = manage_directory_markdown_resource(
        module=module,
        directory=directory,
        primary_filename="SKILL.md",
        frontmatter=build_frontmatter(module),
        body=module.params["body"],
        state=module.params["state"],
        extra_files=module.params.get("extra_files") or {},
    )

    module.exit_json(
        changed=changes.changed,
        directory=directory,
        paths=changes.paths,
        scope=module.params["scope"],
        slug=module.params.get("slug") or slugify(module.params["name"]),
        name=module.params["name"],
    )


if __name__ == "__main__":
    main()
