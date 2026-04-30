#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    manage_named_toml_entry,
    remove_path,
    resolve_scoped_config_path,
    slugify,
    write_toml_if_changed,
)

DOCUMENTATION = r"""
---
module: codex_cli_subagent
short_description: Manage Codex CLI custom subagents
version_added: "1.0.0"
description:
  - Manage Codex CLI custom subagent TOML files in C(~/.codex/agents/) or C(.codex/agents/).
  - Register the subagent in the matching Codex C(config.toml) C([agents]) table so Codex can load it.
options:
  name:
    description:
      - Subagent name.
    type: str
    required: true
  slug:
    description:
      - File name without the C(.toml) suffix.
      - Defaults to a slug derived from C(name).
    type: str
  state:
    description:
      - Whether the subagent should exist.
    type: str
    choices: [present, absent]
    default: present
  scope:
    description:
      - Subagent location scope.
    type: str
    choices: [user, project]
    default: user
  project_dir:
    description:
      - Project root used when C(scope=project).
    type: path
  path:
    description:
      - Exact subagent TOML file to manage.
      - Overrides C(scope), C(project_dir), and C(slug).
    type: path
  config_path:
    description:
      - Exact Codex C(config.toml) path used for the subagent registry entry.
      - Overrides the path inferred from C(scope) and C(project_dir).
    type: path
  config_file:
    description:
      - C(config_file) value to write under C([agents.<slug>]).
      - Defaults to the subagent TOML path relative to the Codex configuration directory when possible.
    type: str
  description:
    description:
      - Human-readable subagent description.
    type: str
  developer_instructions:
    description:
      - Developer instructions for the subagent.
    type: str
  nickname_candidates:
    description:
      - Optional nickname candidates.
    type: list
    elements: str
  model:
    description:
      - Optional model identifier.
    type: str
  model_reasoning_effort:
    description:
      - Optional reasoning effort setting.
    type: str
  sandbox_mode:
    description:
      - Optional sandbox mode.
    type: str
  mcp_servers:
    description:
      - Optional list of MCP servers exposed to the subagent.
    type: list
    elements: str
  extra:
    description:
      - Additional raw keys to merge into the TOML document.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Create a project Codex reviewer subagent
  agentic.agent_configs.codex_cli_subagent:
    name: Reviewer
    scope: project
    project_dir: /srv/my-repo
    description: Review changes and highlight correctness risks.
    developer_instructions: |
      Review diffs carefully and prioritise concrete defects.
    nickname_candidates:
      - reviewer
      - review
    model: gpt-5
    sandbox_mode: workspace-write
    mcp_servers:
      - repo-tools

- name: Remove a user Codex subagent
  agentic.agent_configs.codex_cli_subagent:
    name: Reviewer
    scope: user
    state: absent
"""

RETURN = r"""
path:
  description: Managed subagent file path.
  returned: always
  type: str
config_path:
  description: Managed Codex config path.
  returned: always
  type: str
subagent:
  description: Effective TOML content.
  returned: when state == 'present'
  type: dict
registry:
  description: Effective Codex C([agents.<slug>]) registry entry.
  returned: when state == 'present'
  type: dict
"""


def build_subagent_definition(module: AnsibleModule) -> dict:
    params = module.params
    if not params.get("description"):
        module.fail_json(msg="description is required when state=present")
    if not params.get("developer_instructions"):
        module.fail_json(msg="developer_instructions is required when state=present")
    desired = {
        "name": params["name"],
        "description": params.get("description"),
        "developer_instructions": params.get("developer_instructions"),
        "nickname_candidates": params.get("nickname_candidates"),
        "model": params.get("model"),
        "model_reasoning_effort": params.get("model_reasoning_effort"),
        "sandbox_mode": params.get("sandbox_mode"),
        "mcp_servers": params.get("mcp_servers"),
    }
    desired.update(params.get("extra") or {})
    return clean_dict(desired)


def build_registry_definition(
    module: AnsibleModule, subagent_path: str, config_path: str
) -> dict:
    params = module.params
    desired = {
        "description": params.get("description"),
        "config_file": params.get("config_file")
        or resolve_config_file(subagent_path, config_path),
        "nickname_candidates": params.get("nickname_candidates"),
    }
    return clean_dict(desired)


def resolve_config_file(subagent_path: str, config_path: str) -> str:
    expanded_subagent_path = os.path.abspath(os.path.expanduser(subagent_path))
    expanded_config_dir = os.path.dirname(
        os.path.abspath(os.path.expanduser(config_path))
    )
    try:
        common_path = os.path.commonpath([expanded_subagent_path, expanded_config_dir])
    except ValueError:
        return expanded_subagent_path
    if common_path != expanded_config_dir:
        return expanded_subagent_path
    return os.path.relpath(expanded_subagent_path, expanded_config_dir)


def resolve_subagent_path(module: AnsibleModule) -> str:
    if module.params.get("path"):
        return module.params["path"]
    slug = module.params.get("slug") or slugify(module.params["name"])
    try:
        return resolve_scoped_config_path(
            path=None,
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path=os.path.join("~/.codex/agents", slug + ".toml"),
            project_relative_path=os.path.join(".codex/agents", slug + ".toml"),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))


def resolve_config_path(module: AnsibleModule) -> str:
    try:
        return resolve_scoped_config_path(
            path=module.params.get("config_path"),
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path="~/.codex/config.toml",
            project_relative_path=os.path.join(".codex", "config.toml"),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))


def main() -> None:
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
            "config_path": {"type": "path"},
            "config_file": {"type": "str"},
            "description": {"type": "str"},
            "developer_instructions": {"type": "str"},
            "nickname_candidates": {"type": "list", "elements": "str"},
            "model": {"type": "str"},
            "model_reasoning_effort": {"type": "str"},
            "sandbox_mode": {"type": "str"},
            "mcp_servers": {"type": "list", "elements": "str"},
            "extra": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )

    path = resolve_subagent_path(module)
    config_path = resolve_config_path(module)
    slug = module.params.get("slug") or slugify(module.params["name"])
    if module.params["state"] == "absent":
        changed_file = remove_path(module, path, recursive=False)
        changed_registry, data = manage_named_toml_entry(
            module=module,
            path=config_path,
            root_key="agents",
            name=slug,
            desired=None,
            state="absent",
        )
        module.exit_json(
            changed=(changed_file or changed_registry),
            path=path,
            config_path=config_path,
            scope=module.params["scope"],
            slug=slug,
            name=module.params["name"],
            agents=data.get("agents", {}),
        )

    subagent = build_subagent_definition(module)
    registry = build_registry_definition(module, path, config_path)
    changed_file = write_toml_if_changed(module, path, subagent)
    changed_registry, data = manage_named_toml_entry(
        module=module,
        path=config_path,
        root_key="agents",
        name=slug,
        desired=registry,
        state="present",
    )
    module.exit_json(
        changed=(changed_file or changed_registry),
        path=path,
        config_path=config_path,
        scope=module.params["scope"],
        slug=slug,
        name=module.params["name"],
        subagent=subagent,
        registry=data.get("agents", {}).get(slug, registry),
    )


if __name__ == "__main__":
    main()
