"""Manage Claude Code skill directories.

The claude_code_skill.py Ansible module creates, updates, or removes Claude
Code skills that contain a ``SKILL.md`` file and optional support files. Use it
to provision repeatable user-scoped or project-scoped skills with parameters
such as ``name``, ``scope``, ``project_dir``, ``description``,
``allowed_tools``, ``metadata``, ``body``, and ``extra_files``.

Example playbook task::

    - name: Install a project Claude Code skill
      agentic.agent_configs.claude_code_skill:
        name: Release checklist
        scope: project
        project_dir: /srv/my-repo
        description: Run the release checklist and verify artefacts.
        allowed_tools:
          - Bash
          - Read
        body: |
          Follow the release checklist in docs/release.md.
"""

#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: claude_code_skill
short_description: Manage Claude Code skills
version_added: "1.0.0"
description:
  - Manage Claude Code skill directories containing C(SKILL.md) and optional support files.
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
  allowed_tools:
    description:
      - Optional Claude Code C(allowed-tools) front matter entry.
    type: list
    elements: str
  disable_model_invocation:
    description:
      - Optional Claude Code C(disable-model-invocation) front matter entry.
    type: bool
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
- name: Install a project-scoped Claude skill
  agentic.agent_configs.claude_code_skill:
    name: Release checklist
    scope: project
    project_dir: /srv/my-repo
    description: Run the release checklist and verify artefacts.
    allowed_tools:
      - Bash
      - Read
    body: |
      Follow the release checklist in docs/release.md.
    extra_files:
      references/release.md: |
        Keep this skill aligned with the release process.

- name: Remove a user Claude skill
  agentic.agent_configs.claude_code_skill:
    name: Release checklist
    scope: user
    state: absent
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

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    manage_directory_markdown_resource,
    merge_dicts,
    normalize_mapping_order,
    resolve_scoped_config_path,
    slugify,
)


def build_frontmatter(module: AnsibleModule) -> dict:
    params = module.params
    if params["state"] == "present" and not params.get("description"):
        module.fail_json(msg="description is required when state=present")
    base = {
        "name": params["name"],
        "description": params.get("description"),
        "allowed-tools": params.get("allowed_tools"),
        "disable-model-invocation": params.get("disable_model_invocation"),
    }
    return normalize_mapping_order(
        merge_dicts(base, params.get("metadata") or {}),
        ["name", "description", "allowed-tools", "disable-model-invocation"],
    )


def resolve_directory(module: AnsibleModule) -> str:
    if module.params.get("path"):
        return module.params["path"]
    slug = module.params.get("slug") or slugify(module.params["name"])
    try:
        base_path = resolve_scoped_config_path(
            path=None,
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path=os.path.join("~/.claude/skills", slug),
            project_relative_path=os.path.join(".claude/skills", slug),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))
    return base_path


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "name": {"type": "str", "required": True},
            "slug": {"type": "str"},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "scope": {"type": "str", "choices": ["user", "project"], "default": "user"},
            "project_dir": {"type": "path"},
            "path": {"type": "path"},
            "description": {"type": "str"},
            "body": {"type": "str", "default": ""},
            "allowed_tools": {"type": "list", "elements": "str"},
            "disable_model_invocation": {"type": "bool"},
            "metadata": {"type": "dict", "default": {}},
            "extra_files": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )

    directory = resolve_directory(module)
    frontmatter = build_frontmatter(module)
    changes = manage_directory_markdown_resource(
        module=module,
        directory=directory,
        primary_filename="SKILL.md",
        frontmatter=frontmatter,
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
