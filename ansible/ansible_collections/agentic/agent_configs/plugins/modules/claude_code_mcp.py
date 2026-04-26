"""Manage Claude Code Model Context Protocol server definitions.

This Ansible module creates, updates, or removes Claude Code MCP server
configuration in user-scoped ``~/.claude.json`` files or project-scoped
``.mcp.json`` files. Use it to provision repeatable integrations for stdio,
HTTP, or Server-Sent Events transports with parameters such as ``name``,
``scope``, ``transport``, ``command``, ``args``, ``env``, ``url``, ``headers``,
and ``headers_helper``.

Example playbook task::

    - name: Configure a project stdio MCP server
      agentic.agent_configs.claude_code_mcp:
        name: repo-tools
        scope: project
        project_dir: /srv/my-repo
        transport: stdio
        command: /usr/local/bin/repo-tools-mcp
        args:
          - --stdio
"""

#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: claude_code_mcp
short_description: Manage Claude Code MCP server definitions
version_added: "1.0.0"
description:
  - Manage Claude Code MCP servers in C(~/.claude.json) or project C(.mcp.json) files.
options:
  name:
    description:
      - MCP server name.
    type: str
    required: true
  state:
    description:
      - Whether the MCP server should exist.
    type: str
    choices: [present, absent]
    default: present
  scope:
    description:
      - Configuration scope.
      - C(project) writes to C(.mcp.json).
      - C(user) writes to C(~/.claude.json).
    type: str
    choices: [user, project]
    default: user
  project_dir:
    description:
      - Project root used when C(scope=project).
    type: path
  path:
    description:
      - Exact config file to manage.
      - Overrides C(scope) and C(project_dir).
    type: path
  transport:
    description:
      - MCP transport type.
    type: str
    choices: [stdio, http, sse]
  command:
    description:
      - Executable used for C(stdio) servers.
    type: str
  args:
    description:
      - Arguments for C(stdio) servers.
    type: list
    elements: str
    default: []
  env:
    description:
      - Environment variables for C(stdio) servers.
    type: dict
    default: {}
  url:
    description:
      - URL for C(http) or C(sse) servers.
    type: str
  headers:
    description:
      - HTTP headers for C(http) or C(sse) servers.
    type: dict
    default: {}
  headers_helper:
    description:
      - Optional headers helper command supported by Claude Code HTTP MCP definitions.
    type: str
  extra:
    description:
      - Additional raw keys to merge into the MCP server definition.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Configure a shared Claude Code stdio MCP server
  agentic.agent_configs.claude_code_mcp:
    name: repo-tools
    scope: project
    project_dir: /srv/my-repo
    transport: stdio
    command: /usr/local/bin/repo-tools-mcp
    args:
      - --stdio
    env:
      LOG_LEVEL: info

- name: Configure a user-scoped Claude Code HTTP MCP server
  agentic.agent_configs.claude_code_mcp:
    name: stripe
    scope: user
    transport: http
    url: https://mcp.stripe.com
    headers:
      X-Env: prod
"""

RETURN = r"""
path:
  description: Managed configuration path.
  returned: always
  type: str
server:
  description: Effective server definition.
  returned: when state == 'present'
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    manage_named_json_entry,
    resolve_scoped_config_path,
)


def build_server_definition(module: AnsibleModule) -> dict:
    params = module.params
    transport = params.get("transport")
    extra = params.get("extra") or {}

    if transport is None:
        module.fail_json(msg="transport is required when state=present")

    if transport == "stdio":
        command = params.get("command")
        if not command:
            module.fail_json(msg="command is required when transport=stdio")
        desired = {
            "command": command,
            "args": params.get("args") or [],
            "env": params.get("env") or {},
        }
    else:
        url = params.get("url")
        if not url:
            module.fail_json(msg="url is required when transport is http or sse")
        desired = {
            "type": transport,
            "url": url,
            "headers": params.get("headers") or {},
            "headersHelper": params.get("headers_helper"),
        }

    desired.update(extra)
    return clean_dict(desired)


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "name": {"type": "str", "required": True},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "scope": {"type": "str", "choices": ["user", "project"], "default": "user"},
            "project_dir": {"type": "path"},
            "path": {"type": "path"},
            "transport": {"type": "str", "choices": ["stdio", "http", "sse"]},
            "command": {"type": "str"},
            "args": {"type": "list", "elements": "str", "default": []},
            "env": {"type": "dict", "default": {}},
            "url": {"type": "str"},
            "headers": {"type": "dict", "default": {}},
            "headers_helper": {"type": "str"},
            "extra": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )

    state = module.params["state"]
    try:
        path = resolve_scoped_config_path(
            path=module.params.get("path"),
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path="~/.claude.json",
            project_relative_path=".mcp.json",
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    desired = None
    if state == "present":
        desired = build_server_definition(module)

    changed, data = manage_named_json_entry(
        module=module,
        path=path,
        root_key="mcpServers",
        name=module.params["name"],
        desired=desired,
        state=state,
    )

    result = {
        "changed": changed,
        "path": path,
        "scope": module.params["scope"],
        "name": module.params["name"],
    }
    if state == "present":
        result["server"] = data.get("mcpServers", {}).get(module.params["name"], desired)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
