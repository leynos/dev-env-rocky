#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Manage DeepSeek-TUI Model Context Protocol server definitions.

This module performs read-modify-write updates on ``mcp.json``. Serialise
parallel writes externally, for example by running the play with ``serial: 1``
when several hosts or tasks can target the same file.
"""

from __future__ import annotations

import os
from typing import Any

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    load_json_file,
    log_operation,
    manage_named_json_entry,
    resolve_scoped_config_path,
)

DOCUMENTATION = r"""
---
module: deepseek_tui_mcp
short_description: Manage DeepSeek-TUI MCP server definitions
version_added: "1.0.0"
description:
  - Manage DeepSeek-TUI MCP server definitions in C(~/.deepseek/mcp.json) or C(.deepseek/mcp.json).
  - DeepSeek-TUI v0.8.24 reads C(servers) and also accepts C(mcpServers); this module writes the native C(servers) key.
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
    default: []
  env:
    description:
      - Environment variables for C(stdio) servers.
    type: dict
    default: {}
  url:
    description:
      - URL for C(http) servers.
    type: str
  disabled:
    description:
      - Whether the server is disabled.
    type: bool
  enabled:
    description:
      - Whether the server is enabled.
    type: bool
  required:
    description:
      - Whether startup validation should fail when this server cannot initialise.
    type: bool
  connect_timeout:
    description:
      - Per-server connection timeout in seconds.
    type: int
  execute_timeout:
    description:
      - Per-server tool execution timeout in seconds.
    type: int
  read_timeout:
    description:
      - Per-server read timeout in seconds.
    type: int
  enabled_tools:
    description:
      - Optional allow-list of tool names.
    type: list
    elements: str
  disabled_tools:
    description:
      - Optional deny-list of tool names.
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
- name: Configure a DeepSeek-TUI stdio MCP server
  agentic.agent_configs.deepseek_tui_mcp:
    name: repo-tools
    transport: stdio
    command: /usr/local/bin/repo-tools-mcp
    args:
      - --stdio

- name: Configure a project DeepSeek-TUI HTTP MCP server
  agentic.agent_configs.deepseek_tui_mcp:
    name: internal-api
    scope: project
    project_dir: /srv/my-repo
    transport: http
    url: http://localhost:3000/mcp
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


def build_server_definition(
    *,
    transport: str,
    command: str | None,
    args: list[str],
    env: dict[str, object],
    url: str | None,
    disabled: bool | None,
    enabled: bool | None,
    required: bool | None,
    connect_timeout: int | None,
    execute_timeout: int | None,
    read_timeout: int | None,
    enabled_tools: list[str] | None,
    disabled_tools: list[str] | None,
    extra: dict[str, object],
) -> dict[str, object]:
    """Build a DeepSeek-TUI MCP server definition from domain parameters."""
    if transport == "stdio":
        desired: dict[str, object] = {
            "command": command,
            "args": args,
            "env": env,
        }
    else:
        desired = {"url": url}

    desired.update(
        clean_dict(
            {
                "disabled": disabled,
                "enabled": enabled,
                "required": required,
                "connect_timeout": connect_timeout,
                "execute_timeout": execute_timeout,
                "read_timeout": read_timeout,
                "enabled_tools": enabled_tools,
                "disabled_tools": disabled_tools,
            }
        )
    )
    desired.update(extra)
    return clean_dict(desired)


def validate_present_server_params(params: dict[str, Any]) -> None:
    """Validate MCP parameters that are required only when the server exists."""
    transport = params.get("transport")
    if transport is None:
        msg = (
            "transport is required when state=present "
            f"name={params.get('name')!r} scope={params.get('scope')!r}"
        )
        raise ValueError(msg)
    if transport == "stdio":
        command = params.get("command")
        if not command:
            msg = (
                "command is required when transport=stdio "
                f"name={params.get('name')!r} scope={params.get('scope')!r}"
            )
            raise ValueError(msg)
    else:
        url = params.get("url")
        if not url:
            msg = (
                "url is required when transport=http "
                f"name={params.get('name')!r} scope={params.get('scope')!r}"
            )
            raise ValueError(msg)


def state_transition(changed: bool, existed_before: bool, state: str) -> str:
    """Return a compact state transition label for module results."""
    if not changed:
        return "unchanged"
    if state == "absent":
        return "removed" if existed_before else "unchanged"
    return "updated" if existed_before else "created"


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
            "transport": {"type": "str", "choices": ["stdio", "http"]},
            "command": {"type": "str"},
            "args": {"type": "list", "elements": "str", "default": []},
            "env": {"type": "dict", "default": {}},
            "url": {"type": "str"},
            "disabled": {"type": "bool"},
            "enabled": {"type": "bool"},
            "required": {"type": "bool"},
            "connect_timeout": {"type": "int"},
            "execute_timeout": {"type": "int"},
            "read_timeout": {"type": "int"},
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
            user_path="~/.deepseek/mcp.json",
            project_relative_path=os.path.join(".deepseek", "mcp.json"),
        )
    except ValueError as exc:
        module.fail_json(
            msg=(
                "failed to resolve DeepSeek-TUI MCP path "
                f"name={module.params.get('name')!r} "
                f"scope={module.params.get('scope')!r}: {exc}"
            )
        )

    desired = None
    if module.params["state"] == "present":
        try:
            validate_present_server_params(module.params)
        except ValueError as exc:
            module.fail_json(msg=str(exc))
        desired = build_server_definition(
            transport=module.params["transport"],
            command=module.params.get("command"),
            args=module.params.get("args") or [],
            env=module.params.get("env") or {},
            url=module.params.get("url"),
            disabled=module.params.get("disabled"),
            enabled=module.params.get("enabled"),
            required=module.params.get("required"),
            connect_timeout=module.params.get("connect_timeout"),
            execute_timeout=module.params.get("execute_timeout"),
            read_timeout=module.params.get("read_timeout"),
            enabled_tools=module.params.get("enabled_tools"),
            disabled_tools=module.params.get("disabled_tools"),
            extra=module.params.get("extra") or {},
        )

    existing_data = {}
    try:
        existing_data = load_json_file(path, default={})
    except Exception:
        existing_data = {}
    existing_servers = (
        existing_data.get("servers", {}) if isinstance(existing_data, dict) else {}
    )
    existed_before = (
        isinstance(existing_servers, dict) and module.params["name"] in existing_servers
    )
    changed, data = manage_named_json_entry(
        module=module,
        path=path,
        root_key="servers",
        name=module.params["name"],
        desired=desired,
        state=module.params["state"],
    )

    result = {
        "changed": changed,
        "path": path,
        "scope": module.params["scope"],
        "name": module.params["name"],
        "state_transition": state_transition(
            changed, existed_before, module.params["state"]
        ),
    }
    if module.params["state"] == "present":
        result["server"] = data.get("servers", {}).get(module.params["name"], desired)

    log_operation(
        module,
        "deepseek_tui_mcp",
        action=result["state_transition"],
        path=path,
        name=module.params["name"],
        scope=module.params["scope"],
        state=module.params["state"],
        changed=changed,
    )
    module.exit_json(**result)


if __name__ == "__main__":
    main()
