#!/usr/bin/python
from __future__ import annotations

import re

from ansible.module_utils.basic import AnsibleModule


UV_LIST_RE = re.compile(r"^(?P<name>\S+)\s+v(?P<version>\S+)(?:\s|$)")


def resolve_binary(module: AnsibleModule, value: str) -> str:
    path = module.get_bin_path(value, required=False)
    if path:
        return path
    module.fail_json(msg=f"Could not find executable: {value}")


def run(module: AnsibleModule, cmd: list[str]):
    rc, stdout, stderr = module.run_command(cmd)
    return rc, stdout, stderr


def read_installed_tools(module: AnsibleModule, uv_bin: str) -> dict[str, str]:
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


def main():
    module = AnsibleModule(
        argument_spec={
            "name": {"type": "str", "required": True},
            "version": {"type": "str", "required": False, "default": None},
            "spec": {"type": "str", "required": False, "default": None},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "uv_path": {"type": "str", "default": "uv"},
            "python": {"type": "str", "required": False, "default": None},
            "with_packages": {"type": "list", "elements": "str", "default": []},
            "force": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )

    params = module.params
    uv_bin = resolve_binary(module, params["uv_path"])

    installed = read_installed_tools(module, uv_bin)
    installed_version = installed.get(params["name"])

    if params["state"] == "absent":
        if installed_version is None:
            module.exit_json(changed=False, name=params["name"], state="absent")

        cmd = [uv_bin, "tool", "uninstall", params["name"]]
        if module.check_mode:
            module.exit_json(changed=True, name=params["name"], state="absent", cmd=cmd)

        rc, stdout, stderr = run(module, cmd)
        if rc != 0:
            module.fail_json(
                msg=f"Failed to uninstall uv tool {params['name']}",
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
        )

    install_target = params["spec"]
    if not install_target:
        install_target = (
            f"{params['name']}=={params['version']}"
            if params["version"]
            else params["name"]
        )

    cmd = [uv_bin, "tool", "install"]
    if params["force"]:
        cmd.append("--force")
    if params["python"]:
        cmd.extend(["--python", params["python"]])
    for pkg in params["with_packages"]:
        cmd.extend(["--with", pkg])
    cmd.append(install_target)

    if module.check_mode:
        module.exit_json(
            changed=True,
            name=params["name"],
            state="present",
            previous_version=installed_version,
            target=install_target,
            cmd=cmd,
        )

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
    module.exit_json(
        changed=True,
        name=params["name"],
        state="present",
        previous_version=installed_version,
        installed_version=installed_after.get(params["name"]),
        target=install_target,
        cmd=cmd,
        stdout=stdout,
        stderr=stderr,
    )


if __name__ == "__main__":
    main()
