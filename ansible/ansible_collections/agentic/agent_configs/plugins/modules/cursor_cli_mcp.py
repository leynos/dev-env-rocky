"""Manage Cursor CLI Model Context Protocol server definitions.

This Ansible module creates, updates, or removes Cursor MCP server
configuration in user-scoped ``~/.cursor/mcp.json`` files or project-scoped
``.cursor/mcp.json`` files. Cursor CLI uses the same MCP configuration as the
editor, so these entries are discovered by the ``agent`` binary.
"""

#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: cursor_cli_mcp
short_description: Manage Cursor CLI MCP server definitions
version_added: "1.0.0"
description:
  - Manage Cursor MCP servers in C(~/.cursor/mcp.json) or project C(.cursor/mcp.json) files.
  - Cursor CLI discovers the same MCP configuration as the Cursor editor.
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
    type: str
    choices: [user, project]
    default: user
  project_dir:
    description:
      - Project root used when C(scope=project).
    type: path
  path:
    description:
      - Exact C(mcp.json) path to manage.
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
  extra:
    description:
      - Additional raw keys to merge into the MCP server definition.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Configure a user Cursor stdio MCP server
  agentic.agent_configs.cursor_cli_mcp:
    name: repo-tools
    scope: user
    transport: stdio
    command: /usr/local/bin/repo-tools-mcp
    args:
      - --stdio
    env:
      LOG_LEVEL: info

- name: Configure a project Cursor HTTP MCP server
  agentic.agent_configs.cursor_cli_mcp:
    name: internal-api
    scope: project
    project_dir: /srv/my-repo
    transport: http
    url: https://mcp.internal.example/v1
    headers:
      Authorization: "Bearer ${env:INTERNAL_MCP_TOKEN}"
"""

RETURN = r"""
path:
  description: Managed Cursor MCP config path.
  returned: always
  type: str
server:
  description: Effective server definition.
  returned: when state == 'present'
  type: dict
"""

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    manage_named_json_entry,
    resolve_scoped_config_path,
)


_SENSITIVE_KEYS = {"env", "headers"}


def _redact_server(server: dict) -> dict:
    """Return a copy of the server dict with sensitive keys replaced by 'REDACTED'."""
    return {k: ("REDACTED" if k in _SENSITIVE_KEYS and v else v) for k, v in server.items()}


def build_server_definition(module: AnsibleModule) -> dict:
    """Build the Cursor MCP server definition from module parameters."""
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
        }

    desired.update(extra)
    return clean_dict(desired)


def main() -> None:
    """Run the Ansible module."""
    module = AnsibleModule(
        argument_spec={
            "name": {"type": "str", "required": True},
            "state": {
                "type": "str",
                "choices": ["present", "absent"],
                "default": "present",
            },
            "scope": {"type": "str", "choices": ["user", "project"], "default": "user"},
            "project_dir": {"type": "path"},
            "path": {"type": "path"},
            "transport": {"type": "str", "choices": ["stdio", "http", "sse"]},
            "command": {"type": "str"},
            "args": {"type": "list", "elements": "str", "default": []},
            "env": {"type": "dict", "default": {}},
            "url": {"type": "str"},
            "headers": {"type": "dict", "default": {}},
            "extra": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )

    try:
        path = resolve_scoped_config_path(
            path=module.params.get("path"),
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path="~/.cursor/mcp.json",
            project_relative_path=os.path.join(".cursor", "mcp.json"),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    desired = None
    if module.params["state"] == "present":
        desired = build_server_definition(module)

    changed, data = manage_named_json_entry(
        module=module,
        path=path,
        root_key="mcpServers",
        name=module.params["name"],
        desired=desired,
        state=module.params["state"],
    )

    result = {
        "changed": changed,
        "path": path,
        "scope": module.params["scope"],
        "name": module.params["name"],
    }
    if module.params["state"] == "present":
        server = data.get("mcpServers", {}).get(module.params["name"], desired)
        result["server"] = _redact_server(server)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
