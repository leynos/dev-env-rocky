#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Manage Factory Droid custom droid Markdown files.

The factory_droid_droid.py Ansible module creates, updates, or removes custom
Factory Droid droids in user-scoped ``~/.factory/droids`` directories or
project-scoped ``.factory/droids`` directories. Use it to provision repeatable
droid prompts with front matter such as ``name``, ``description``, ``model``,
``reasoning_effort``, ``tools``, and additional ``metadata``. The module builds
front matter with ``build_frontmatter``, resolves the managed file path with
``resolve_path``, and writes the requested Markdown body from ``main``.

Example playbook task::

    - name: Create a project Factory Droid reviewer
      agentic.agent_configs.factory_droid_droid:
        name: Reviewer
        scope: project
        project_dir: /srv/my-repo
        description: Review changes and identify concrete risks.
        model: inherit
        reasoning_effort: high
        tools:
          - Read
          - Edit
          - Execute
        body: |
          Review the supplied changes and highlight correctness issues.
"""
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    manage_markdown_file,
    merge_dicts,
    normalize_mapping_order,
    resolve_scoped_config_path,
    slugify,
)

DOCUMENTATION = r"""
---
module: factory_droid_droid
short_description: Manage Factory Droid custom droids
version_added: "1.0.0"
description:
  - Manage Factory Droid custom droid Markdown files in C(~/.factory/droids/) or C(.factory/droids/).
options:
  name:
    description:
      - Droid name.
    type: str
    required: true
  slug:
    description:
      - File name without the C(.md) suffix.
      - Defaults to a slug derived from C(name).
    type: str
  state:
    description:
      - Whether the droid should exist.
    type: str
    choices: [present, absent]
    default: present
  scope:
    description:
      - Droid location scope.
    type: str
    choices: [user, project]
    default: user
  project_dir:
    description:
      - Project root used when C(scope=project).
    type: path
  path:
    description:
      - Exact droid Markdown file to manage.
      - Overrides C(scope), C(project_dir), and C(slug).
    type: path
  description:
    description:
      - Optional droid description.
    type: str
  body:
    description:
      - Markdown body for the droid prompt.
    type: str
    default: ''
  model:
    description:
      - Optional model identifier, or C(inherit).
    type: str
  reasoning_effort:
    description:
      - Optional reasoning effort value.
    type: str
  tools:
    description:
      - Optional tools setting.
      - May be a category string such as C(read-only) or an explicit list of tool names.
    type: raw
  metadata:
    description:
      - Additional front matter keys.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Create a project Factory Droid reviewer
  agentic.agent_configs.factory_droid_droid:
    name: Reviewer
    scope: project
    project_dir: /srv/my-repo
    description: Review changes and identify concrete risks.
    model: inherit
    reasoning_effort: high
    tools:
      - Read
      - Edit
      - Execute
    body: |
      Review the supplied changes and highlight correctness issues.

- name: Remove a user Factory Droid custom droid
  agentic.agent_configs.factory_droid_droid:
    name: Reviewer
    scope: user
    state: absent
"""

RETURN = r"""
path:
  description: Managed droid file path.
  returned: always
  type: str
"""

def build_frontmatter(module: AnsibleModule) -> dict:
    """Build Factory Droid front matter from module parameters."""
    params = module.params
    if params["state"] == "present" and not params["body"].strip():
        module.fail_json(msg="body must be non-empty when state=present")
    base = {
        "name": params["name"],
        "description": params.get("description"),
        "model": params.get("model"),
        "reasoningEffort": params.get("reasoning_effort"),
        "tools": params.get("tools"),
    }
    return normalize_mapping_order(
        merge_dicts(base, params.get("metadata") or {}),
        ["name", "description", "model", "reasoningEffort", "tools"],
    )


def resolve_path(module: AnsibleModule) -> str:
    """Resolve the managed Factory Droid file path."""
    if module.params.get("path"):
        return module.params["path"]
    slug = module.params.get("slug") or slugify(module.params["name"])
    try:
        return resolve_scoped_config_path(
            path=None,
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path=os.path.join("~/.factory/droids", slug + ".md"),
            project_relative_path=os.path.join(".factory/droids", slug + ".md"),
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
            "model": {"type": "str"},
            "reasoning_effort": {"type": "str"},
            "tools": {"type": "raw"},
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
