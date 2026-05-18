#!/usr/bin/python
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Manage Python command-line tools installed with uv.

The uv_tool.py Ansible module creates, updates, or removes tools managed by
``uv tool`` while reporting the command it ran or would run in check mode. Use
it to keep user-level Python tooling repeatable with parameters such as
``name``, ``version``, ``spec``, ``python``, ``with_packages``,
``with_executables_from``, ``force``, and ``state``. The module resolves the
``uv`` executable, reads installed tool
versions from ``uv tool list``, and applies installs or removals from ``main``.

Example playbook task::

    - name: Install ruff with uv
      agentic.agent_configs.uv_tool:
        name: ruff
        version: 0.14.0
        python: "3.12"
"""

import re
from typing import Any

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: uv_tool
short_description: Manage uv-installed tools
version_added: "1.0.0"
description:
  - Install and remove tools managed by C(uv tool).
  - Installed versions are detected from C(uv tool list).
options:
  name:
    description:
      - Tool name to manage.
    type: str
    required: true
  version:
    description:
      - Exact package version to install when C(spec) is omitted.
      - When omitted, any installed version satisfies C(state=present).
    type: str
  spec:
    description:
      - Explicit package spec passed to C(uv tool install).
      - Overrides the spec derived from C(name) and C(version).
    type: str
  state:
    description:
      - Whether the tool should be installed or absent.
    type: str
    choices: [present, absent]
    default: present
  uv_path:
    description:
      - uv executable path or name to resolve on C(PATH).
    type: str
    default: uv
  python:
    description:
      - Python interpreter constraint passed with C(--python).
    type: str
  with_packages:
    description:
      - Extra packages passed with repeated C(--with) options.
    type: list
    elements: str
    default: []
  with_executables_from:
    description:
      - Packages passed with repeated C(--with-executables-from) options.
      - Use this when dependency package executables must be linked into the
        installed tool environment.
    type: list
    elements: str
    default: []
  force:
    description:
      - Pass C(--force) to C(uv tool install).
    type: bool
    default: false
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Install an exact uv tool version
  agentic.agent_configs.uv_tool:
    name: ruff
    version: 0.14.0
    python: '3.14'

- name: Install a uv tool from an explicit spec
  agentic.agent_configs.uv_tool:
    name: my-tool
    spec: git+https://example.invalid/tools/my-tool
    with_packages:
      - requests

- name: Install ansible with ansible-core executables linked
  agentic.agent_configs.uv_tool:
    name: ansible
    with_executables_from:
      - ansible-core,ansible-lint

- name: Remove a uv tool
  agentic.agent_configs.uv_tool:
    name: ruff
    state: absent
"""

RETURN = r"""
name:
  description: Tool name that was managed.
  returned: always
  type: str
state:
  description: Final requested tool state.
  returned: always
  type: str
previous_version:
  description: Version detected before a change was made.
  returned: when changed and a previous version was installed
  type: str
installed_version:
  description: Version detected after installation, or the already-installed version.
  returned: when state == 'present'
  type: str
target:
  description: Package spec passed to C(uv tool install).
  returned: when state == 'present' and a change is needed
  type: str
cmd:
  description: Command executed or that would be executed in check mode.
  returned: when changed
  type: list
  elements: str
stdout:
  description: Command standard output.
  returned: when a command is executed
  type: str
stderr:
  description: Command standard error.
  returned: when a command is executed
  type: str
"""

UV_LIST_RE = re.compile(r"^(?P<name>\S+)\s+v(?P<version>\S+)(?:\s|$)")


def resolve_binary(module: AnsibleModule, value: str) -> str:
    """Resolve and return the path to a named uv binary."""
    path = module.get_bin_path(value, required=False)
    if path:
        return path
    module.fail_json(msg=f"Could not find executable: {value}")


def run(module: AnsibleModule, cmd: list[str]):
    """Run a command using the Ansible module runner and return its output."""
    rc, stdout, stderr = module.run_command(cmd)
    return rc, stdout, stderr


def read_installed_tools(module: AnsibleModule, uv_bin: str) -> dict[str, str]:
    """Return a mapping of installed uv tool names to their versions."""
    rc, stdout, stderr = run(module, [uv_bin, "tool", "list"])
    if rc != 0:
        module.fail_json(
            msg="Failed to query installed uv tools",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
            cmd=[uv_bin, "tool", "list"],
        )

    tools: dict[str, str] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        match = UV_LIST_RE.match(line)
        if match:
            tools[match.group("name")] = match.group("version")
    return tools


def build_install_target(params: dict[str, Any]) -> str:
    """Return the package specifier passed to uv tool install."""
    if params["spec"]:
        return params["spec"]
    if params["version"]:
        return f"{params['name']}=={params['version']}"
    return params["name"]


def build_install_cmd(
    params: dict[str, Any], uv_bin: str, install_target: str
) -> list[str]:
    """Return the uv tool install command for the requested parameters."""
    cmd = [uv_bin, "tool", "install"]
    if params["force"]:
        cmd.append("--force")
    if params["python"]:
        cmd.extend(["--python", params["python"]])
    for pkg in params["with_packages"]:
        cmd.extend(["--with", pkg])
    for pkg in params["with_executables_from"]:
        cmd.extend(["--with-executables-from", pkg])
    cmd.append(install_target)
    return cmd


def _uninstall_tool(
    module: AnsibleModule,
    params: dict[str, Any],
    uv_bin: str,
    installed_version: str | None,
) -> dict[str, Any]:
    """Remove a uv tool when it is installed."""
    if installed_version is None:
        return {"changed": False, "name": params["name"], "state": "absent"}

    cmd = [uv_bin, "tool", "uninstall", params["name"]]
    if module.check_mode:
        return {"changed": True, "name": params["name"], "state": "absent", "cmd": cmd}

    rc, stdout, stderr = run(module, cmd)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to uninstall uv tool {params['name']}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
            cmd=cmd,
        )

    return {
        "changed": True,
        "name": params["name"],
        "state": "absent",
        "previous_version": installed_version,
        "cmd": cmd,
        "stdout": stdout,
        "stderr": stderr,
    }


def _install_tool(
    module: AnsibleModule,
    params: dict[str, Any],
    uv_bin: str,
    installed_version: str | None,
) -> dict[str, Any]:
    """Install or update a uv tool when the desired version is missing."""
    desired_version = params["version"]
    if installed_version is not None and (
        desired_version is None or installed_version == desired_version
    ):
        return {
            "changed": False,
            "name": params["name"],
            "state": "present",
            "installed_version": installed_version,
        }

    install_target = build_install_target(params)
    cmd = build_install_cmd(params, uv_bin, install_target)
    if module.check_mode:
        return {
            "changed": True,
            "name": params["name"],
            "state": "present",
            "previous_version": installed_version,
            "target": install_target,
            "cmd": cmd,
        }

    rc, stdout, stderr = run(module, cmd)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to install uv tool {params['name']}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
            cmd=cmd,
        )

    installed_after = read_installed_tools(module, uv_bin)
    return {
        "changed": True,
        "name": params["name"],
        "state": "present",
        "previous_version": installed_version,
        "installed_version": installed_after.get(params["name"]),
        "target": install_target,
        "cmd": cmd,
        "stdout": stdout,
        "stderr": stderr,
    }


def main():
    """Run the Ansible module."""
    module = AnsibleModule(
        argument_spec={
            "name": {"type": "str", "required": True},
            "version": {"type": "str", "required": False, "default": None},
            "spec": {"type": "str", "required": False, "default": None},
            "state": {
                "type": "str",
                "choices": ["present", "absent"],
                "default": "present",
            },
            "uv_path": {"type": "str", "default": "uv"},
            "python": {"type": "str", "required": False, "default": None},
            "with_packages": {"type": "list", "elements": "str", "default": []},
            "with_executables_from": {
                "type": "list",
                "elements": "str",
                "default": [],
            },
            "force": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )

    params = module.params
    uv_bin = resolve_binary(module, params["uv_path"])
    installed = read_installed_tools(module, uv_bin)
    installed_version = installed.get(params["name"])

    if params["state"] == "absent":
        payload = _uninstall_tool(module, params, uv_bin, installed_version)
    else:
        payload = _install_tool(module, params, uv_bin, installed_version)
    module.exit_json(**payload)


if __name__ == "__main__":
    main()
