#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Manage Codex CLI command hook configuration.

This Ansible module creates, updates, or removes Codex CLI command hooks in
user-scoped ``~/.codex/hooks.json`` files or project-scoped
``.codex/hooks.json`` files. It is useful for provisioning repeatable Codex
automation such as session start hooks, stop hooks, or tool-use checks, and it
also enables the matching Codex hooks feature flag in ``config.toml`` when
hooks are present. Common inputs include ``agent_executable``, ``scope``,
``project_dir``, ``event``, ``matcher``, ``command``, ``timeout``,
``status_message``, ``async_hook``, and ``extra``.

Example playbook task::

    - name: Install a project Codex Stop hook
      agentic.agent_configs.codex_cli_hook:
        agent_executable: /home/payton/.local/bin/codex
        scope: project
        project_dir: /srv/my-repo
        event: Stop
        command: /srv/my-repo/.codex/hooks/stop.sh
        timeout: 30
"""
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    load_toml_file,
    manage_hook_json,
    maybe_validate_executable,
    resolve_scoped_config_path,
    write_toml_if_changed,
)

DOCUMENTATION = r"""
---
module: codex_cli_hook
short_description: Manage Codex CLI command hooks
version_added: "1.0.0"
description:
  - Manage Codex CLI command hooks in C(~/.codex/hooks.json) or C(.codex/hooks.json).
  - When creating hooks, the module also ensures C([features] codex_hooks = true) in the corresponding Codex C(config.toml).
  - This module currently manages command hooks and requires an explicit Codex executable path.
options:
  agent_executable:
    description:
      - Path to the Codex CLI executable associated with this hook configuration.
      - The current implementation stores and optionally validates this path, but edits the configuration files directly.
    type: path
    required: true
  validate_agent_executable:
    description:
      - Validate that C(agent_executable) exists and is executable.
    type: bool
    default: false
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
      - Exact C(hooks.json) path to manage.
      - Overrides C(scope) and C(project_dir).
    type: path
  config_path:
    description:
      - Exact C(config.toml) path used for the Codex feature flag.
      - Overrides the path inferred from C(scope) and C(project_dir).
    type: path
  event:
    description:
      - Codex hook event name.
    type: str
    required: true
  matcher:
    description:
      - Optional matcher for the event.
    type: str
  command:
    description:
      - Shell command to execute for the hook.
      - This is also used as the hook identity within an event and matcher group.
    type: str
    required: true
  timeout:
    description:
      - Optional timeout in seconds.
    type: int
  status_message:
    description:
      - Optional status message displayed by Codex while the hook runs.
    type: str
  async_hook:
    description:
      - Whether Codex should treat the command hook as asynchronous.
      - Codex currently skips asynchronous command hooks, so leave this disabled for blocking quality gates.
    type: bool
    default: false
  extra:
    description:
      - Additional raw keys to merge into the hook definition.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Add a Codex PostToolUse hook
  agentic.agent_configs.codex_cli_hook:
    agent_executable: /home/payton/.local/bin/codex
    scope: project
    project_dir: /srv/my-repo
    event: PostToolUse
    matcher: Bash
    command: /srv/my-repo/.codex/hooks/post-bash.sh
    status_message: Running repository checks

- name: Add a Codex SessionStart hook
  agentic.agent_configs.codex_cli_hook:
    agent_executable: /home/payton/.local/bin/codex
    scope: user
    event: SessionStart
    command: /home/payton/.codex/hooks/session-start.sh
    timeout: 30

- name: Remove a Codex hook
  agentic.agent_configs.codex_cli_hook:
    agent_executable: /home/payton/.local/bin/codex
    scope: user
    event: Stop
    command: /usr/local/bin/notify-codex-stop
    state: absent
"""

RETURN = r"""
path:
  description: Managed hooks.json path.
  returned: always
  type: str
config_path:
  description: Managed config.toml path used for the feature flag.
  returned: always
  type: str
hook:
  description: Effective hook entry.
  returned: when state == 'present'
  type: dict
"""

def build_hook_definition(module: AnsibleModule) -> dict:
    """Build a Codex CLI hook definition from module parameters."""
    params = module.params
    desired = {
        "type": "command",
        "command": params["command"],
        "timeout": params.get("timeout"),
        "async": params.get("async_hook"),
        "statusMessage": params.get("status_message"),
    }
    desired.update(params.get("extra") or {})
    return clean_dict(desired)


def ensure_feature_flag(module: AnsibleModule, config_path: str) -> bool:
    """Enable the codex_hooks feature flag in the Codex config file."""
    data = load_toml_file(module, config_path, default={})
    if not isinstance(data, dict):
        module.fail_json(msg="Expected TOML root object in %s" % config_path)
    features = data.setdefault("features", {})
    if not isinstance(features, dict):
        module.fail_json(msg="Expected [features] to be a table in %s" % config_path)
    if features.get("codex_hooks") is True:
        return False
    features["codex_hooks"] = True
    if module.check_mode:
        return True
    write_toml_if_changed(module, config_path, data)
    return True


def main() -> None:
    """Run the Ansible module."""
    module = AnsibleModule(
        argument_spec={
            "agent_executable": {"type": "path", "required": True},
            "validate_agent_executable": {"type": "bool", "default": False},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "scope": {"type": "str", "choices": ["user", "project"], "default": "user"},
            "project_dir": {"type": "path"},
            "path": {"type": "path"},
            "config_path": {"type": "path"},
            "event": {"type": "str", "required": True},
            "matcher": {"type": "str"},
            "command": {"type": "str", "required": True},
            "timeout": {"type": "int"},
            "status_message": {"type": "str"},
            "async_hook": {"type": "bool", "default": False},
            "extra": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )

    maybe_validate_executable(
        module,
        module.params["agent_executable"],
        module.params["validate_agent_executable"],
    )

    try:
        hooks_path = resolve_scoped_config_path(
            path=module.params.get("path"),
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path="~/.codex/hooks.json",
            project_relative_path=os.path.join(".codex", "hooks.json"),
        )
        config_path = resolve_scoped_config_path(
            path=module.params.get("config_path"),
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path="~/.codex/config.toml",
            project_relative_path=os.path.join(".codex", "config.toml"),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    desired = build_hook_definition(module)
    changed_hook, data = manage_hook_json(
        module=module,
        path=hooks_path,
        event=module.params["event"],
        matcher=module.params.get("matcher"),
        desired_hook=desired,
        state=module.params["state"],
        identity_keys=("type", "command"),
    )

    changed_flag = False
    if module.params["state"] == "present":
        changed_flag = ensure_feature_flag(module, config_path)

    module.exit_json(
        changed=(changed_hook or changed_flag),
        path=hooks_path,
        config_path=config_path,
        scope=module.params["scope"],
        event=module.params["event"],
        matcher=module.params.get("matcher"),
        command=module.params["command"],
        agent_executable=module.params["agent_executable"],
        hook=desired if module.params["state"] == "present" else None,
        hooks=data.get("hooks", {}),
        feature_flag_set=(module.params["state"] == "present"),
    )


if __name__ == "__main__":
    main()
