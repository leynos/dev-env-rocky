#!/usr/bin/python
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import annotations

DOCUMENTATION = r"""
---
module: bun_global
short_description: Manage Bun global packages
version_added: "1.0.0"
description:
  - Install and remove Bun global packages with idempotence based on the installed package version.
options:
  name:
    description:
      - Package name to manage.
      - Scoped package names such as C(@scope/tool) are supported.
    type: str
    required: true
  version:
    description:
      - Exact package version to install.
      - When omitted, any installed version satisfies C(state=present).
    type: str
  state:
    description:
      - Whether the package should be installed or absent.
    type: str
    choices: [present, absent]
    default: present
  bun_path:
    description:
      - Bun executable path or name to resolve on C(PATH).
    type: str
    default: bun
  global_dir:
    description:
      - Bun global install directory.
      - Defaults to C(BUN_INSTALL_GLOBAL_DIR), then C(~/.bun/install/global).
    type: path
  global_bin_dir:
    description:
      - Bun global binary directory.
      - Defaults to C(BUN_INSTALL_BIN), then C(~/.bun/bin).
    type: path
  ignore_scripts:
    description:
      - Pass C(--ignore-scripts) when installing packages.
    type: bool
    default: false
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Install an exact Bun package version
  agentic.agent_configs.bun_global:
    name: '@scope/tool'
    version: 1.2.3
    ignore_scripts: true

- name: Remove a Bun global package
  agentic.agent_configs.bun_global:
    name: '@scope/tool'
    state: absent
"""

RETURN = r"""
name:
  description: Package name that was managed.
  returned: always
  type: str
state:
  description: Final requested package state.
  returned: always
  type: str
global_dir:
  description: Bun global install directory used for version detection.
  returned: always
  type: str
global_bin_dir:
  description: Bun global binary directory.
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
  description: Package spec passed to C(bun install -g).
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

import json
import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.bun_paths import resolve_global_bin_dir, resolve_global_dir


def resolve_binary(module: AnsibleModule, value: str) -> str:
    path = module.get_bin_path(value, required=False)
    if path:
        return path
    module.fail_json(msg=f"Could not find executable: {value}")


def run(module: AnsibleModule, cmd: list[str], env: dict[str, str] | None = None):
    rc, stdout, stderr = module.run_command(cmd, environ_update=env or {})
    return rc, stdout, stderr


def package_json_path(global_dir: str, package_name: str) -> str:
    return os.path.join(global_dir, "node_modules", *package_name.split("/"), "package.json")


def read_installed_version(pkg_json: str) -> str | None:
    if not os.path.exists(pkg_json):
        return None
    with open(pkg_json, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("version")


def main():
    module = AnsibleModule(
        argument_spec={
            "name": {"type": "str", "required": True},
            "version": {"type": "str", "required": False, "default": None},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "bun_path": {"type": "str", "default": "bun"},
            "global_dir": {"type": "path", "required": False, "default": None},
            "global_bin_dir": {"type": "path", "required": False, "default": None},
            "ignore_scripts": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )

    params = module.params
    bun_bin = resolve_binary(module, params["bun_path"])

    global_dir = resolve_global_dir(params["global_dir"])
    global_bin_dir = resolve_global_bin_dir(params["global_bin_dir"])
    pkg_json = package_json_path(global_dir, params["name"])
    installed_version = read_installed_version(pkg_json)

    if params["state"] == "absent":
        if installed_version is None:
            module.exit_json(
                changed=False,
                name=params["name"],
                state="absent",
                global_dir=global_dir,
                global_bin_dir=global_bin_dir,
            )

        cmd = [bun_bin, "remove", "-g", params["name"]]

        if module.check_mode:
            module.exit_json(
                changed=True,
                name=params["name"],
                state="absent",
                global_dir=global_dir,
                global_bin_dir=global_bin_dir,
                cmd=cmd,
            )

        rc, stdout, stderr = run(module, cmd)
        if rc != 0:
            module.fail_json(
                msg=f"Failed to remove Bun global package {params['name']}",
                rc=rc,
                stdout=stdout,
                stderr=stderr,
                cmd=cmd,
            )

        module.exit_json(
            changed=True,
            name=params["name"],
            state="absent",
            previous_version=installed_version,
            global_dir=global_dir,
            global_bin_dir=global_bin_dir,
            cmd=cmd,
            stdout=stdout,
            stderr=stderr,
        )

    # state == present
    desired_version = params["version"]
    if installed_version is not None and (desired_version is None or installed_version == desired_version):
        module.exit_json(
            changed=False,
            name=params["name"],
            state="present",
            installed_version=installed_version,
            global_dir=global_dir,
            global_bin_dir=global_bin_dir,
        )

    target = f"{params['name']}@{params['version']}" if params["version"] else params["name"]
    cmd = [bun_bin, "install", "-g"]
    if params["ignore_scripts"]:
        cmd.append("--ignore-scripts")
    cmd.append(target)

    if module.check_mode:
        module.exit_json(
            changed=True,
            name=params["name"],
            state="present",
            previous_version=installed_version,
            target=target,
            global_dir=global_dir,
            global_bin_dir=global_bin_dir,
            cmd=cmd,
        )

    rc, stdout, stderr = run(module, cmd)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to install Bun global package {params['name']}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
            cmd=cmd,
        )

    installed_after = read_installed_version(pkg_json)

    module.exit_json(
        changed=True,
        name=params["name"],
        state="present",
        previous_version=installed_version,
        installed_version=installed_after,
        target=target,
        global_dir=global_dir,
        global_bin_dir=global_bin_dir,
        cmd=cmd,
        stdout=stdout,
        stderr=stderr,
    )


if __name__ == "__main__":
    main()
