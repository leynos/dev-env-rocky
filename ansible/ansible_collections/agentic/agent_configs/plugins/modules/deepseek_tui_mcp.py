#!/usr/bin/python
"""Manage DeepSeek-TUI Model Context Protocol server definitions.

This module performs read-modify-write updates on ``mcp.json``. Serialise
parallel writes externally, for example by running the play with ``serial: 1``
when several hosts or tasks can target the same file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class ServerParams:
    """Value object encapsulating the parameters of one DeepSeek-TUI MCP server."""

    transport: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, Any] = field(default_factory=dict)
    url: str | None = None
    disabled: bool | None = None
    enabled: bool | None = None
    required: bool | None = None
    connect_timeout: int | None = None
    execute_timeout: int | None = None
    read_timeout: int | None = None
    enabled_tools: list[str] | None = None
    disabled_tools: list[str] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def build_server_definition(params: ServerParams) -> dict[str, Any]:
    """Build a DeepSeek-TUI MCP server definition from domain parameters."""
    if params.transport == "stdio":
        desired: dict[str, Any] = {
            "command": params.command,
            "args": params.args,
            "env": params.env,
        }
    else:
        desired = {"url": params.url}

    desired.update(
        clean_dict(
            {
                "disabled": params.disabled,
                "enabled": params.enabled,
                "required": params.required,
                "connect_timeout": params.connect_timeout,
                "execute_timeout": params.execute_timeout,
                "read_timeout": params.read_timeout,
                "enabled_tools": params.enabled_tools,
                "disabled_tools": params.disabled_tools,
            }
        )
    )
    desired.update(params.extra)
    return clean_dict(desired)


def _validate_stdio_params(params: dict[str, Any]) -> None:
    """Raise ValueError if the stdio transport is missing its required command."""
    command = params.get("command")
    if not command:
        msg = (
            "command is required when transport=stdio "
            f"name={params.get('name')!r} scope={params.get('scope')!r}"
        )
        raise ValueError(msg)


def _validate_http_params(params: dict[str, Any]) -> None:
    """Raise ValueError if the http transport is missing its required url."""
    url = params.get("url")
    if not url:
        msg = (
            "url is required when transport=http "
            f"name={params.get('name')!r} scope={params.get('scope')!r}"
        )
        raise ValueError(msg)


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
        _validate_stdio_params(params)
    else:
        _validate_http_params(params)


def state_transition(changed: bool, existed_before: bool, state: str) -> str:
    """Return a compact state transition label for module results."""
    if not changed:
        return "unchanged"
    if state == "absent":
        return "removed" if existed_before else "unchanged"
    return "updated" if existed_before else "created"


def _resolve_mcp_path(module: AnsibleModule) -> str:
    """Resolve the effective mcp.json path, failing the module on error."""
    try:
        return resolve_scoped_config_path(
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


def _build_desired_server(module: AnsibleModule) -> dict[str, Any] | None:
    """Validate params and build the desired server definition; return None for state=absent."""
    if module.params["state"] != "present":
        return None
    try:
        validate_present_server_params(module.params)
    except ValueError as exc:
        module.fail_json(msg=str(exc))
    server_params = ServerParams(
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
    return build_server_definition(server_params)


def _check_existed_before(path: str, name: str) -> bool:
    """Return True if a server entry named *name* already exists in *path*."""
    try:
        existing_data = load_json_file(path, default={})
    except Exception:
        return False
    if not isinstance(existing_data, dict):
        return False
    existing_servers = existing_data.get("servers", {})
    return isinstance(existing_servers, dict) and name in existing_servers


def _assemble_result(
    module: AnsibleModule,
    *,
    changed: bool,
    existed_before: bool,
    path: str,
    data: dict[str, Any],
    desired: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble the module result dictionary."""
    result: dict[str, Any] = {
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
    return result


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
        required_if=[
            ["state", "present", ["transport"]],
            ["transport", "stdio", ["command"]],
            ["transport", "http", ["url"]],
        ],
        supports_check_mode=True,
    )

    path = _resolve_mcp_path(module)
    desired = _build_desired_server(module)
    existed_before = _check_existed_before(path, module.params["name"])

    changed, data = manage_named_json_entry(
        module=module,
        path=path,
        root_key="servers",
        name=module.params["name"],
        desired=desired,
        state=module.params["state"],
    )

    result = _assemble_result(
        module,
        changed=changed,
        existed_before=existed_before,
        path=path,
        data=data,
        desired=desired,
    )
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
