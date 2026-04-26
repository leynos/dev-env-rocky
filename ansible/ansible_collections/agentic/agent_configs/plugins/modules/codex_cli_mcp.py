"""Manage Codex CLI Model Context Protocol server definitions.

This Ansible module creates, updates, or removes Codex CLI MCP server
configuration in user-scoped ``~/.codex/config.toml`` files or project-scoped
``.codex/config.toml`` files. Use it to provision repeatable stdio or HTTP MCP
integrations with parameters such as ``name``, ``scope``, ``transport``,
``command``, ``args``, ``env``, ``env_vars``, ``cwd``, ``url``,
``bearer_token_env_var``, ``http_headers``, ``enabled_tools``, and ``extra``.

Example playbook task::

    - name: Configure a project Codex stdio MCP server
      agentic.agent_configs.codex_cli_mcp:
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
module: codex_cli_mcp
short_description: Manage Codex CLI MCP server definitions
version_added: "1.0.0"
description:
  - Manage Codex CLI MCP server definitions in C(~/.codex/config.toml) or C(.codex/config.toml).
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
      - Exact C(config.toml) path to manage.
      - Overrides C(scope) and C(project_dir).
    type: path
  transport:
    description:
      - MCP transport type.
      - Codex infers the transport from the fields written.
    type: str
    choices: [stdio, http]
  command:
    description:
      - Executable used for C(stdio) servers.
    type: str
  args:
    description:
      - Arguments for C(stdio) servers.
    type: list
    elements: str
  env:
    description:
      - Explicit environment variables for C(stdio) servers.
    type: dict
    default: {}
  env_vars:
    description:
      - Environment variable names to inherit for C(stdio) servers.
    type: list
    elements: str
  cwd:
    description:
      - Working directory for C(stdio) servers.
    type: path
  url:
    description:
      - URL for C(http) servers.
    type: str
  bearer_token_env_var:
    description:
      - Environment variable containing the bearer token for C(http) servers.
    type: str
  http_headers:
    description:
      - Static headers for C(http) servers.
    type: dict
    default: {}
  env_http_headers:
    description:
      - Mapping of header names to environment variable names for C(http) servers.
    type: dict
    default: {}
  startup_timeout_sec:
    description:
      - Optional startup timeout.
    type: int
  tool_timeout_sec:
    description:
      - Optional per-tool timeout.
    type: int
  enabled:
    description:
      - Whether the server is enabled.
    type: bool
  required:
    description:
      - Whether the server is required.
    type: bool
  enabled_tools:
    description:
      - Optional allow-list of tools.
    type: list
    elements: str
  disabled_tools:
    description:
      - Optional deny-list of tools.
    type: list
    elements: str
  extra:
    description:
      - Additional raw keys to merge into the MCP server definition.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Configure a project Codex stdio MCP server
  agentic.agent_configs.codex_cli_mcp:
    name: repo-tools
    scope: project
    project_dir: /srv/my-repo
    transport: stdio
    command: /usr/local/bin/repo-tools-mcp
    args: [--stdio]
    env:
      LOG_LEVEL: info

- name: Configure a user Codex HTTP MCP server
  agentic.agent_configs.codex_cli_mcp:
    name: internal-api
    scope: user
    transport: http
    url: https://mcp.internal.example/v1
    bearer_token_env_var: INTERNAL_MCP_TOKEN
"""

RETURN = r"""
path:
  description: Managed Codex config path.
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
    manage_named_toml_entry,
    resolve_scoped_config_path,
)


def build_server_definition(module: AnsibleModule) -> dict:
    params = module.params
    transport = params.get("transport")
    extra = params.get("extra") or {}

    if transport is None:
        module.fail_json(msg="transport is required when state=present")

    common = {
        "startup_timeout_sec": params.get("startup_timeout_sec"),
        "tool_timeout_sec": params.get("tool_timeout_sec"),
        "enabled": params.get("enabled"),
        "required": params.get("required"),
        "enabled_tools": params.get("enabled_tools"),
        "disabled_tools": params.get("disabled_tools"),
    }

    if transport == "stdio":
        command = params.get("command")
        if not command:
            module.fail_json(msg="command is required when transport=stdio")
        desired = {
            "command": command,
            "args": params.get("args"),
            "env": params.get("env") or {},
            "env_vars": params.get("env_vars"),
            "cwd": params.get("cwd"),
        }
    else:
        url = params.get("url")
        if not url:
            module.fail_json(msg="url is required when transport=http")
        desired = {
            "url": url,
            "bearer_token_env_var": params.get("bearer_token_env_var"),
            "http_headers": params.get("http_headers") or {},
            "env_http_headers": params.get("env_http_headers") or {},
        }

    desired.update(clean_dict(common))
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
            "transport": {"type": "str", "choices": ["stdio", "http"]},
            "command": {"type": "str"},
            "args": {"type": "list", "elements": "str"},
            "env": {"type": "dict", "default": {}},
            "env_vars": {"type": "list", "elements": "str"},
            "cwd": {"type": "path"},
            "url": {"type": "str"},
            "bearer_token_env_var": {"type": "str", "no_log": True},
            "http_headers": {"type": "dict", "default": {}},
            "env_http_headers": {"type": "dict", "default": {}},
            "startup_timeout_sec": {"type": "int"},
            "tool_timeout_sec": {"type": "int"},
            "enabled": {"type": "bool"},
            "required": {"type": "bool"},
            "enabled_tools": {"type": "list", "elements": "str"},
            "disabled_tools": {"type": "list", "elements": "str"},
            "extra": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )

    try:
        path = resolve_scoped_config_path(
            path=module.params.get("path"),
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path="~/.codex/config.toml",
            project_relative_path=os.path.join(".codex", "config.toml"),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    desired = None
    if module.params["state"] == "present":
        desired = build_server_definition(module)

    changed, data = manage_named_toml_entry(
        module=module,
        path=path,
        root_key="mcp_servers",
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
        result["server"] = data.get("mcp_servers", {}).get(module.params["name"], desired)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
