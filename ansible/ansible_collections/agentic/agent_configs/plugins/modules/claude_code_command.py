#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Manage Claude Code slash command Markdown files.

This Ansible module creates, updates, or removes Claude Code command files in
user or project scopes while preserving predictable front matter and command
body content. It is useful for provisioning shared slash commands across
developer machines and repositories. Expected inputs include ``name``,
``description``, ``body``, ``scope``, optional ``project_dir`` or ``path``, and
``state``; outputs include the managed command ``path`` and normal Ansible
change status.

Example playbook task::

    - name: Create a project command
      agentic.agent_configs.claude_code_command:
        name: Deploy
        scope: project
        project_dir: /srv/my-repo
        description: Run the deployment workflow.
        body: Deploy this service using scripts/deploy.

Example ad-hoc call::

    ansible localhost -m agentic.agent_configs.claude_code_command \\
      -a "name=Deploy description='Run deployment' body='Deploy this service'"
"""

from __future__ import annotations

DOCUMENTATION = r"""
---
module: claude_code_command
short_description: Manage Claude Code slash commands
version_added: "1.0.0"
description:
  - Manage Claude Code slash command Markdown files in C(.claude/commands/) or C(~/.claude/commands/).
options:
  name:
    description:
      - Command display name.
    type: str
    required: true
  slug:
    description:
      - File name without the C(.md) suffix.
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
      - Exact command Markdown file to manage.
      - Overrides C(scope), C(project_dir), and C(slug).
    type: path
  description:
    description:
      - Command description used in front matter.
    type: str
  body:
    description:
      - Markdown body for the command file.
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
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Create a project slash command
  agentic.agent_configs.claude_code_command:
    name: Deploy
    scope: project
    project_dir: /srv/my-repo
    description: Run the project deployment workflow.
    body: |
      Deploy this service using the scripts in scripts/deploy.

- name: Remove a user slash command
  agentic.agent_configs.claude_code_command:
    name: Deploy
    scope: user
    state: absent
"""

RETURN = r"""
path:
  description: Managed command path.
  returned: always
  type: str
"""

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    manage_markdown_file,
    merge_dicts,
    normalize_mapping_order,
    resolve_scoped_config_path,
    slugify,
)


def build_frontmatter(module: AnsibleModule) -> dict:
    """Build Claude Code command front matter from module parameters."""
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


def resolve_path(module: AnsibleModule) -> str:
    """Resolve the managed Claude command file path."""
    if module.params.get("path"):
        return module.params["path"]
    slug = module.params.get("slug") or slugify(module.params["name"])
    try:
        path = resolve_scoped_config_path(
            path=None,
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path=os.path.join("~/.claude/commands", slug + ".md"),
            project_relative_path=os.path.join(".claude/commands", slug + ".md"),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))
    return path


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
            "allowed_tools": {"type": "list", "elements": "str"},
            "disable_model_invocation": {"type": "bool"},
            "metadata": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )

    path = resolve_path(module)
    changed = manage_markdown_file(
        module=module,
        path=path,
        frontmatter=build_frontmatter(module),
        body=module.params["body"],
        state=module.params["state"],
    )

    module.exit_json(
        changed=changed,
        path=path,
        scope=module.params["scope"],
        slug=module.params.get("slug") or slugify(module.params["name"]),
        name=module.params["name"],
    )


if __name__ == "__main__":
    main()
