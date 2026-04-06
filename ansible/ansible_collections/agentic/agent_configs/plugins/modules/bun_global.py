#!/usr/bin/python
from __future__ import annotations

import json
import os

from ansible.module_utils.basic import AnsibleModule


def resolve_binary(module: AnsibleModule, value: str) -> str:
    path = module.get_bin_path(value, required=False)
    if path:
        return path
    module.fail_json(msg=f"Could not find executable: {value}")


def run(module: AnsibleModule, cmd: list[str], env: dict[str, str] | None = None):
    rc, stdout, stderr = module.run_command(cmd, environ_update=env or {})
    return rc, stdout, stderr


def resolve_global_dir(param_value: str | None) -> str:
    if param_value:
        return os.path.expanduser(param_value)
    env_value = os.environ.get("BUN_INSTALL_GLOBAL_DIR")
    if env_value:
        return os.path.expanduser(env_value)
    return os.path.expanduser("~/.bun/install/global")


def resolve_global_bin_dir(param_value: str | None) -> str:
    if param_value:
        return os.path.expanduser(param_value)
    env_value = os.environ.get("BUN_INSTALL_BIN")
    if env_value:
        return os.path.expanduser(env_value)
    return os.path.expanduser("~/.bun/bin")


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
            "global_dir": {"type": "str", "required": False, "default": None},
            "global_bin_dir": {"type": "str", "required": False, "default": None},
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
