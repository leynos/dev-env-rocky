#!/usr/bin/python
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Manage Bun global packages for packaging tools playbooks.

The bun_global Ansible module installs, updates, and removes Bun global
packages while preserving idempotence through installed package metadata. Use
``name``, ``spec``, ``version``, ``state``, ``global_dir``, ``global_bin_dir``, and
``trust_postinstall`` to control the requested package, the Bun installation
paths, and selective post-install script trust.

Example task::

    - name: Install Biome with Bun
      packaging.tools.bun_global:
        name: '@biomejs/biome'
        version: 2.3.8
        state: present
"""

from __future__ import annotations

import json
import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.bun_paths import (
    resolve_global_bin_dir,
    resolve_global_dir,
)

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
  spec:
    description:
      - Explicit package specifier to pass to C(bun install -g).
      - Use this for git URLs or tarballs whose installed package name differs from the install target.
      - Mutually exclusive with C(version).
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
  trust_postinstall:
    description:
      - Run C(bun pm trust) for this package after ensuring it is installed.
      - Use this only for packages whose post-install scripts should be trusted.
    type: bool
    default: false
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Install an exact Bun package version
  packaging.tools.bun_global:
    name: '@scope/tool'
    version: 1.2.3
    ignore_scripts: true

- name: Install a package and trust its post-install scripts
  packaging.tools.bun_global:
    name: '@scope/tool'
    trust_postinstall: true

- name: Remove a Bun global package
  packaging.tools.bun_global:
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
trust_cmd:
  description: Command executed, or that would be executed in check mode, to trust package scripts.
  returned: when trust_postinstall is true and trust is needed
  type: list
  elements: str
trust_stdout:
  description: Trust command standard output.
  returned: when a trust command is executed
  type: str
trust_stderr:
  description: Trust command standard error.
  returned: when a trust command is executed
  type: str
"""


def resolve_binary(module: AnsibleModule, value: str) -> str:
    path = module.get_bin_path(value, required=False)
    if path:
        return path
    module.fail_json(msg=f"Could not find executable: {value}")


def run(
    module: AnsibleModule,
    cmd: list[str],
    env: dict[str, str] | None = None,
    cwd: str | None = None,
):
    rc, stdout, stderr = module.run_command(cmd, environ_update=env or {}, cwd=cwd)
    return rc, stdout, stderr


def package_json_path(global_dir: str, package_name: str) -> str:
    return os.path.join(
        global_dir, "node_modules", *package_name.split("/"), "package.json"
    )


def read_installed_version(pkg_json: str) -> str | None:
    if not os.path.exists(pkg_json):
        return None
    with open(pkg_json, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("version")


def is_trusted_dependency(global_dir: str, package_name: str) -> bool:
    pkg_json = os.path.join(global_dir, "package.json")
    if not os.path.exists(pkg_json):
        return False
    with open(pkg_json, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    trusted_dependencies = data.get("trustedDependencies", [])
    return (
        isinstance(trusted_dependencies, list) and package_name in trusted_dependencies
    )


def trust_result_is_idempotent(stderr: str) -> bool:
    return "0 scripts ran" in stderr and (
        "already trusted" in stderr or "don't have scripts to run" in stderr
    )


def main():
    module = AnsibleModule(
        argument_spec={
            "name": {"type": "str", "required": True},
            "spec": {"type": "str", "required": False, "default": None},
            "version": {"type": "str", "required": False, "default": None},
            "state": {
                "type": "str",
                "choices": ["present", "absent"],
                "default": "present",
            },
            "bun_path": {"type": "str", "default": "bun"},
            "global_dir": {"type": "path", "required": False, "default": None},
            "global_bin_dir": {"type": "path", "required": False, "default": None},
            "ignore_scripts": {"type": "bool", "default": False},
            "trust_postinstall": {"type": "bool", "default": False},
        },
        mutually_exclusive=[("spec", "version")],
        supports_check_mode=True,
    )

    params = module.params
    bun_bin = resolve_binary(module, params["bun_path"])

    global_dir = resolve_global_dir(params["global_dir"])
    global_bin_dir = resolve_global_bin_dir(params["global_bin_dir"])
    bun_env = {
        "BUN_INSTALL_GLOBAL_DIR": global_dir,
        "BUN_INSTALL_BIN": global_bin_dir,
    }
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

        rc, stdout, stderr = run(module, cmd, env=bun_env)
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
    needs_install = installed_version is None or (
        desired_version is not None and installed_version != desired_version
    )
    trust_needed = params["trust_postinstall"] and not is_trusted_dependency(
        global_dir, params["name"]
    )
    if not needs_install and not trust_needed:
        module.exit_json(
            changed=False,
            name=params["name"],
            state="present",
            installed_version=installed_version,
            global_dir=global_dir,
            global_bin_dir=global_bin_dir,
        )

    target = params["spec"] or (
        f"{params['name']}@{params['version']}" if params["version"] else params["name"]
    )
    cmd = [bun_bin, "install", "-g"]
    if params["ignore_scripts"]:
        cmd.append("--ignore-scripts")
    cmd.append(target)
    trust_cmd = [bun_bin, "pm", "trust", params["name"]]

    if module.check_mode:
        result = {
            "changed": True,
            "name": params["name"],
            "state": "present",
            "previous_version": installed_version,
            "target": target,
            "global_dir": global_dir,
            "global_bin_dir": global_bin_dir,
        }
        if needs_install:
            result["cmd"] = cmd
        if trust_needed:
            result["trust_cmd"] = trust_cmd
        module.exit_json(**result)

    stdout = ""
    stderr = ""
    if needs_install:
        rc, stdout, stderr = run(module, cmd, env=bun_env)
        if rc != 0:
            module.fail_json(
                msg=f"Failed to install Bun global package {params['name']}",
                rc=rc,
                stdout=stdout,
                stderr=stderr,
                cmd=cmd,
            )

    trust_stdout = ""
    trust_stderr = ""
    if trust_needed:
        trust_rc, trust_stdout, trust_stderr = run(
            module, trust_cmd, env=bun_env, cwd=global_dir
        )
        if trust_rc != 0 and not trust_result_is_idempotent(trust_stderr):
            module.fail_json(
                msg=f"Failed to trust Bun post-install scripts for package {params['name']}",
                rc=trust_rc,
                stdout=trust_stdout,
                stderr=trust_stderr,
                cmd=trust_cmd,
            )

    installed_after = read_installed_version(pkg_json)

    result = {
        "changed": True,
        "name": params["name"],
        "state": "present",
        "previous_version": installed_version,
        "installed_version": installed_after,
        "target": target,
        "global_dir": global_dir,
        "global_bin_dir": global_bin_dir,
    }
    if needs_install:
        result.update(
            cmd=cmd,
            stdout=stdout,
            stderr=stderr,
        )
    if trust_needed:
        result.update(
            trust_cmd=trust_cmd,
            trust_stdout=trust_stdout,
            trust_stderr=trust_stderr,
        )

    module.exit_json(**result)


if __name__ == "__main__":
    main()
