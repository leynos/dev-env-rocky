"""Manage Factory Droid skill directories.

The factory_droid_skill.py Ansible module creates, updates, or removes Factory
Droid skills that contain a ``SKILL.md`` file and optional support files. Use
it to provision repeatable user-scoped or project-scoped skills with parameters
such as ``name``, ``scope``, ``project_dir``, ``description``, ``body``,
``user_invocable``, ``disable_model_invocation``, ``metadata``, and
``extra_files``. The module builds front matter, resolves the target skill
directory, and writes the requested Markdown resource from ``main``.

Example playbook task::

    - name: Install a project Factory Droid skill
      agentic.agent_configs.factory_droid_skill:
        name: Release helper
        scope: project
        project_dir: /srv/my-repo
        description: Run the release flow and verify artefacts.
        user_invocable: true
        body: |
          Follow docs/release.md and summarise any blockers.
"""

#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: factory_droid_skill
short_description: Manage Factory Droid skills
version_added: "1.0.0"
description:
  - Manage Factory Droid skill directories containing C(SKILL.md) and optional support files.
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
  user_invocable:
    description:
      - Optional Factory Droid C(user-invocable) front matter entry.
    type: bool
  disable_model_invocation:
    description:
      - Optional Factory Droid C(disable-model-invocation) front matter entry.
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
- name: Install a project Factory Droid skill
  agentic.agent_configs.factory_droid_skill:
    name: Release helper
    scope: project
    project_dir: /srv/my-repo
    description: Run the release flow and verify artefacts.
    user_invocable: true
    body: |
      Follow docs/release.md and summarise any blockers.

- name: Remove a user Factory Droid skill
  agentic.agent_configs.factory_droid_skill:
    name: Release helper
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
    """Build Factory Droid skill front matter from module parameters."""
    params = module.params
    if params["state"] == "present" and not params.get("description"):
        module.fail_json(msg="description is required when state=present")
    base = {
        "name": params["name"],
        "description": params.get("description"),
        "user-invocable": params.get("user_invocable"),
        "disable-model-invocation": params.get("disable_model_invocation"),
    }
    return normalize_mapping_order(
        merge_dicts(base, params.get("metadata") or {}),
        ["name", "description", "user-invocable", "disable-model-invocation"],
    )


def resolve_directory(module: AnsibleModule) -> str:
    """Resolve the managed Factory Droid skill directory."""
    if module.params.get("path"):
        return module.params["path"]
    slug = module.params.get("slug") or slugify(module.params["name"])
    try:
        return resolve_scoped_config_path(
            path=None,
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path=os.path.join("~/.factory/skills", slug),
            project_relative_path=os.path.join(".factory/skills", slug),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))


def main() -> None:
    """Run the Ansible module."""
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
            "user_invocable": {"type": "bool"},
            "disable_model_invocation": {"type": "bool"},
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
