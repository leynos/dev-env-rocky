#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Manage Claude Code hook entries in settings files.

This Ansible module creates, updates, or removes Claude Code command hooks in
user, project, or local settings JSON files. It is useful for provisioning
repeatable hook behaviour such as formatting after file edits, running stop
checks, or adding notification commands. Expected inputs include
``agent_executable``, ``event``, ``command``, optional ``matcher`` and hook
options, plus ``scope`` or an explicit ``path``; outputs include the managed
settings ``path`` and the effective hook entry when present.

Example playbook task::

    - name: Install a project PostToolUse hook
      agentic.agent_configs.claude_code_hook:
        agent_executable: /home/payton/.local/bin/claude
        scope: project
        project_dir: /srv/my-repo
        event: PostToolUse
        matcher: Edit|Write
        command: /srv/my-repo/.claude/hooks/format.sh
"""

from __future__ import annotations

DOCUMENTATION = r"""
---
module: claude_code_hook
short_description: Manage Claude Code command hooks
version_added: "1.0.0"
description:
  - Manage Claude Code command hooks in user, project, or local settings files.
  - This module currently manages command hooks and requires an explicit Claude executable path.
options:
  agent_executable:
    description:
      - Path to the Claude Code executable associated with this hook configuration.
      - The current implementation stores and optionally validates this path, but edits the JSON settings file directly.
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
      - C(local) writes to C(.claude/settings.local.json).
    type: str
    choices: [user, project, local]
    default: user
  project_dir:
    description:
      - Project root used when C(scope=project) or C(scope=local).
    type: path
  path:
    description:
      - Exact settings file to manage.
      - Overrides C(scope) and C(project_dir).
    type: path
  event:
    description:
      - Claude Code hook event name.
    type: str
    required: true
  matcher:
    description:
      - Optional matcher regular expression for the event.
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
  async:
    description:
      - Whether the hook should run asynchronously.
    type: bool
  shell:
    description:
      - Optional shell to use when invoking the hook.
    type: str
  if_condition:
    description:
      - Optional Claude Code hook C(if) expression.
    type: str
  extra:
    description:
      - Additional raw keys to merge into the hook definition.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Run a formatter after Claude edits files
  agentic.agent_configs.claude_code_hook:
    agent_executable: /home/payton/.local/bin/claude
    scope: project
    project_dir: /srv/my-repo
    event: PostToolUse
    matcher: Edit|Write
    command: /srv/my-repo/.claude/hooks/format.sh
    timeout: 30

- name: Remove a Claude hook
  agentic.agent_configs.claude_code_hook:
    agent_executable: /home/payton/.local/bin/claude
    scope: user
    event: Stop
    command: /usr/local/bin/notify-stop
    state: absent
"""

RETURN = r"""
path:
  description: Managed settings path.
  returned: always
  type: str
hook:
  description: Effective hook entry.
  returned: when state == 'present'
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    manage_hook_json,
    maybe_validate_executable,
    resolve_scoped_config_path,
)


def build_hook_definition(module: AnsibleModule) -> dict:
    params = module.params
    desired = {
        "type": "command",
        "command": params["command"],
        "timeout": params.get("timeout"),
        "async": params.get("async"),
        "shell": params.get("shell"),
        "if": params.get("if_condition"),
    }
    desired.update(params.get("extra") or {})
    return clean_dict(desired)


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "agent_executable": {"type": "path", "required": True},
            "validate_agent_executable": {"type": "bool", "default": False},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "scope": {"type": "str", "choices": ["user", "project", "local"], "default": "user"},
            "project_dir": {"type": "path"},
            "path": {"type": "path"},
            "event": {"type": "str", "required": True},
            "matcher": {"type": "str"},
            "command": {"type": "str", "required": True},
            "timeout": {"type": "int"},
            "async": {"type": "bool"},
            "shell": {"type": "str"},
            "if_condition": {"type": "str"},
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
        path = resolve_scoped_config_path(
            path=module.params.get("path"),
            scope=module.params["scope"],
            project_dir=module.params.get("project_dir"),
            user_path="~/.claude/settings.json",
            project_relative_path=".claude/settings.json",
            local_relative_path=".claude/settings.local.json",
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))

    desired = build_hook_definition(module)
    changed, data = manage_hook_json(
        module=module,
        path=path,
        event=module.params["event"],
        matcher=module.params.get("matcher"),
        desired_hook=desired,
        state=module.params["state"],
        identity_keys=("type", "command"),
    )

    result = {
        "changed": changed,
        "path": path,
        "scope": module.params["scope"],
        "event": module.params["event"],
        "matcher": module.params.get("matcher"),
        "command": module.params["command"],
        "agent_executable": module.params["agent_executable"],
    }
    if module.params["state"] == "present":
        result["hook"] = desired
    result["hooks"] = data.get("hooks", {})

    module.exit_json(**result)


if __name__ == "__main__":
    main()
