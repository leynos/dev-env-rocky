#!/usr/bin/python
from __future__ import annotations

import re

from ansible.module_utils.basic import AnsibleModule


def resolve_binary(module: AnsibleModule, value: str) -> str:
    path = module.get_bin_path(value, required=False)
    if path:
        return path
    module.fail_json(msg=f"Could not find executable: {value}")


def run(module: AnsibleModule, cmd: list[str], env: dict[str, str] | None = None):
    rc, stdout, stderr = module.run_command(cmd, environ_update=env or {})
    return rc, stdout, stderr


def read_installed_version(
    module: AnsibleModule,
    cargo_bin: str,
    crate_name: str,
    env: dict[str, str],
) -> str | None:
    rc, stdout, stderr = run(module, [cargo_bin, "install", "--list"], env=env)
    if rc != 0:
        module.fail_json(
            msg="Failed to query installed Cargo packages",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
            cmd=[cargo_bin, "install", "--list"],
        )

    pattern = re.compile(rf"^{re.escape(crate_name)} v(?P<version>[^:\s]+):$", re.MULTILINE)
    match = pattern.search(stdout)
    return match.group("version") if match else None


def main():
    module = AnsibleModule(
        argument_spec={
            "name": {"type": "str", "required": True},
            "version": {"type": "str", "required": False, "default": None},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "cargo_path": {"type": "str", "default": "cargo"},
            "root": {"type": "str", "required": False, "default": None},
            "no_confirm": {"type": "bool", "default": True},
            "force": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )

    params = module.params
    cargo_bin = resolve_binary(module, params["cargo_path"])

    env: dict[str, str] = {}
    if params["root"]:
        env["CARGO_INSTALL_ROOT"] = params["root"]

    installed_version = read_installed_version(module, cargo_bin, params["name"], env)

    if params["state"] == "absent":
        if installed_version is None:
            module.exit_json(changed=False, name=params["name"], state="absent")

        cmd = [cargo_bin, "uninstall", "--package", params["name"]]
        if params["root"]:
            cmd.extend(["--root", params["root"]])

        if module.check_mode:
            module.exit_json(
                changed=True,
                name=params["name"],
                state="absent",
                cmd=cmd,
            )

        rc, stdout, stderr = run(module, cmd, env=env)
        if rc != 0:
            module.fail_json(
                msg=f"Failed to uninstall Cargo package {params['name']}",
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

    target = f"{params['name']}@{params['version']}" if params["version"] else params["name"]
    cmd = [cargo_bin, "binstall"]
    if params["no_confirm"]:
        cmd.append("--no-confirm")
    if params["force"]:
        cmd.append("--force")
    cmd.append(target)

    if module.check_mode:
        module.exit_json(
            changed=True,
            name=params["name"],
            state="present",
            previous_version=installed_version,
            target=target,
            cmd=cmd,
        )

    rc, stdout, stderr = run(module, cmd, env=env)
    if rc != 0:
        module.fail_json(
            msg=f"Failed to install Cargo package {params['name']}",
            rc=rc,
            stdout=stdout,
            stderr=stderr,
            cmd=cmd,
        )

    installed_after = read_installed_version(module, cargo_bin, params["name"], env)

    module.exit_json(
        changed=True,
        name=params["name"],
        state="present",
        previous_version=installed_version,
        installed_version=installed_after,
        target=target,
        cmd=cmd,
        stdout=stdout,
        stderr=stderr,
    )


if __name__ == "__main__":
    main()
