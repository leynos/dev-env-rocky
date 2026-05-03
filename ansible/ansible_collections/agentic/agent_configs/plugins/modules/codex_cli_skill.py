"""Manage Codex CLI skill directories.

The codex_cli_skill.py Ansible module creates, updates, or removes Codex CLI
skills that contain a ``SKILL.md`` file and optional support files such as
``agents/openai.yaml``. Use it to provision repeatable user-scoped or
project-scoped skills with parameters such as ``name``, ``scope``,
``project_dir``, ``description``, ``metadata``, ``body``, ``openai_yaml``,
``openai_yaml_content``, and ``extra_files``. The module exposes helper
functions such as ``build_frontmatter``, ``resolve_directory``, and
``build_extra_files`` to assemble the managed skill directory before
``main`` applies the requested state.

Example playbook task::

    - name: Install a project Codex CLI skill
      agentic.agent_configs.codex_cli_skill:
        name: Release helper
        scope: project
        project_dir: /srv/my-repo
        description: Run the release process and verify all checks.
        body: |
          Follow docs/release.md and summarise any blockers.
        openai_yaml:
          interface:
            display_name: Release helper
            short_description: Project release workflow
"""

#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: codex_cli_skill
short_description: Manage Codex CLI skills
version_added: "1.0.0"
description:
  - Manage Codex CLI skill directories containing C(SKILL.md) and optional support files.
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
  metadata:
    description:
      - Additional front matter keys.
    type: dict
    default: {}
  openai_yaml:
    description:
      - Structured content for C(agents/openai.yaml).
    type: dict
  openai_yaml_content:
    description:
      - Raw content for C(agents/openai.yaml).
      - Mutually exclusive with C(openai_yaml).
    type: str
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
- name: Install a project Codex skill with interface metadata
  agentic.agent_configs.codex_cli_skill:
    name: Release helper
    scope: project
    project_dir: /srv/my-repo
    description: Run the release process and verify all checks.
    body: |
      Follow docs/release.md and summarise any blockers.
    openai_yaml:
      interface:
        display_name: Release helper
        short_description: Project release workflow
      policy:
        allow_implicit_invocation: true

- name: Remove a user Codex skill
  agentic.agent_configs.codex_cli_skill:
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
    yaml_dump,
)


def build_frontmatter(module: AnsibleModule) -> dict:
    """Build Codex CLI skill front matter from module parameters."""
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
    """Resolve the managed Codex skill directory."""
    if module.params.get("path"):
        return module.params["path"]
    slug = module.params.get("slug") or slugify(module.params["name"])
    try:
        return resolve_scoped_config_path(
            path=None,
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path=os.path.join("~/.agents/skills", slug),
            project_relative_path=os.path.join(".agents/skills", slug),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))


def build_extra_files(module: AnsibleModule) -> dict:
    """Build the extra files dict, including any OpenAI YAML configuration."""
    openai_yaml = module.params.get("openai_yaml")
    openai_yaml_content = module.params.get("openai_yaml_content")
    if openai_yaml and openai_yaml_content:
        module.fail_json(msg="openai_yaml and openai_yaml_content are mutually exclusive")
    files = dict(module.params.get("extra_files") or {})
    if openai_yaml:
        files[os.path.join("agents", "openai.yaml")] = yaml_dump(openai_yaml) + "\n"
    elif openai_yaml_content is not None:
        files[os.path.join("agents", "openai.yaml")] = openai_yaml_content
    return files


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
            "metadata": {"type": "dict", "default": {}},
            "openai_yaml": {"type": "dict"},
            "openai_yaml_content": {"type": "str"},
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
        extra_files=build_extra_files(module),
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
