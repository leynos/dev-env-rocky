#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r'''
---
module: codex_cli_subagent
short_description: Manage Codex CLI custom subagents
version_added: "1.0.0"
description:
  - Manage Codex CLI custom subagent TOML files in C(~/.codex/agents/) or C(.codex/agents/).
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
  - OpenAI
'''

EXAMPLES = r'''
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
'''

RETURN = r'''
path:
  description: Managed subagent file path.
  returned: always
  type: str
subagent:
  description: Effective TOML content.
  returned: when state == 'present'
  type: dict
'''

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    resolve_scoped_config_path,
    slugify,
    write_toml_if_changed,
    remove_path,
)



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



def resolve_path(module: AnsibleModule) -> str:
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

    path = resolve_path(module)
    if module.params["state"] == "absent":
        changed = remove_path(module, path, recursive=False)
        module.exit_json(
            changed=changed,
            path=path,
            scope=module.params["scope"],
            slug=module.params.get("slug") or slugify(module.params["name"]),
            name=module.params["name"],
        )

    subagent = build_subagent_definition(module)
    changed = write_toml_if_changed(module, path, subagent)
    module.exit_json(
        changed=changed,
        path=path,
        scope=module.params["scope"],
        slug=module.params.get("slug") or slugify(module.params["name"]),
        name=module.params["name"],
        subagent=subagent,
    )


if __name__ == "__main__":
    main()
