"""Manage Factory Droid command hooks in scoped settings files.

The factory_droid_hook.py Ansible module creates, updates, or removes Factory
Droid command hook entries in user, project, or local JSON settings files. Use
it to provision repeatable hook configuration for events such as ``PostToolUse``
or ``Stop`` by supplying a Factory Droid executable, an event, an optional
matcher, and the command that should run. The module builds the hook definition
with ``build_hook_definition`` and applies it through ``main`` using the shared
settings-file helpers.

Example playbook task::

    - name: Add a project Factory Droid edit hook
      agentic.agent_configs.factory_droid_hook:
        agent_executable: /usr/local/bin/droid
        scope: project
        project_dir: /srv/my-repo
        event: PostToolUse
        matcher: Edit|Write
        command: /srv/my-repo/.factory/hooks/post-edit.sh
"""

#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: factory_droid_hook
short_description: Manage Factory Droid command hooks
version_added: "1.0.0"
description:
  - Manage Factory Droid command hooks in user, project, or local settings files.
  - This module currently manages command hooks and requires an explicit Factory Droid executable path.
options:
  agent_executable:
    description:
      - Path to the Factory Droid executable associated with this hook configuration.
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
      - C(local) writes to C(.factory/settings.local.json).
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
      - Factory Droid hook event name.
    type: str
    required: true
  matcher:
    description:
      - Optional matcher expression for tool events.
    type: str
  command:
    description:
      - Shell command to execute for the hook.
      - This is also used as the hook identity within an event and matcher group.
    type: str
    required: true
  extra:
    description:
      - Additional raw keys to merge into the hook definition.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Add a Factory Droid PostToolUse hook
  agentic.agent_configs.factory_droid_hook:
    agent_executable: /usr/local/bin/droid
    scope: project
    project_dir: /srv/my-repo
    event: PostToolUse
    matcher: Edit|Write
    command: /srv/my-repo/.factory/hooks/post-edit.sh

- name: Remove a Factory Droid hook
  agentic.agent_configs.factory_droid_hook:
    agent_executable: /usr/local/bin/droid
    scope: user
    event: Stop
    command: /usr/local/bin/notify-droid-stop
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

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    manage_hook_json,
    maybe_validate_executable,
    resolve_scoped_config_path,
)


def build_hook_definition(module: AnsibleModule) -> dict:
    """Build a Factory Droid hook definition from module parameters."""
    desired = {
        "type": "command",
        "command": module.params["command"],
    }
    desired.update(module.params.get("extra") or {})
    return clean_dict(desired)


def main() -> None:
    """Run the Ansible module."""
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
            user_path="~/.factory/settings.json",
            project_relative_path=os.path.join(".factory", "settings.json"),
            local_relative_path=os.path.join(".factory", "settings.local.json"),
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

    module.exit_json(
        changed=changed,
        path=path,
        scope=module.params["scope"],
        event=module.params["event"],
        matcher=module.params.get("matcher"),
        command=module.params["command"],
        agent_executable=module.params["agent_executable"],
        hook=desired if module.params["state"] == "present" else None,
        hooks=data.get("hooks", {}),
    )


if __name__ == "__main__":
    main()
