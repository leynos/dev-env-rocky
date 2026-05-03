Yes. I’d keep them as thin wrappers rather than trying to outsmart the upstream
tools.

The upstream surfaces are just about good enough for that style of module. `uv`
gives you `uv tool install`, `uv tool uninstall`, `uv tool list`, and
`uv tool dir --bin`, and its tool install flow supports things like `--with` and
 `--python`. `cargo-binstall` documents unattended installs with
`cargo binstall --no-confirm` and versioned targets like `crate@version`, while
Cargo itself gives you the query/removal primitives `cargo install --list` and
`cargo uninstall`. Bun documents `bun install -g`, `bun remove -g`, the default
global install location under `~/.bun/install/global`, and the config/env knobs
for overriding global package and bin directories. For the Ansible side, the
normal pattern is `AnsibleModule` plus `run_command()` for external
executables. ([Astral Docs][1])

I’m keeping these deliberately narrow: `state: present|absent`, optional exact
version, check mode, and modest return data. I’ve left out the full
`DOCUMENTATION` / `EXAMPLES` / `RETURN` stanzas to keep the sketches readable.

### `uv_tool.py`

```python
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
```

### `cargo_binstall.py`

```python
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
```

### `bun_global.py`

```python
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
```

A few blunt caveats.

The `uv` module is the least clean one. It uses `uv tool list` as the state
source, which is sensible for a sketch but still depends on human-oriented
output rather than a documented stable machine-readable interface for that
specific command. The docs clearly give you the install/list/uninstall
commands, tool directories, executable directory, and install options; they
just do not document a structured `uv tool list` output contract on the pages I
checked. `uv tool install` also installs by package/tool name, not by
executable name, so `name` should be whatever `uv tool list` reports. ([Astral
Docs][2])

The `cargo_binstall` sketch uses Cargo’s own install database as the source of
truth via `cargo install --list`, and removes with `cargo uninstall`. I expect
that to line up with `cargo-binstall` because binstall explicitly positions
itself as a near drop-in replacement for `cargo install`, but that part is
still an inference rather than a first-party guarantee I found spelled out as a
compatibility contract. Cargo’s install root and uninstall semantics are
documented, though. ([Docs.rs][3])

The `bun_global` sketch is the cleanest structurally, but only if Bun uses its
documented default global directory or you surface the override via
`BUN_INSTALL_GLOBAL_DIR` / `BUN_INSTALL_BIN` or explicit module params. If you
set `install.globalDir` in `bunfig.toml` without exporting the matching
environment variable, pass `global_dir` explicitly so state detection reads the
right `node_modules` tree. Bun documents both the default global location and
those override knobs. ([Bun][4])

A minimal playbook use would look like this:

```yaml
- hosts: all
  tasks:
    - name: Install ruff with uv
      uv_tool:
        name: ruff
        version: "0.5.0"

    - name: Install cargo-nextest with cargo-binstall
      cargo_binstall:
        name: cargo-nextest
        version: "0.9.86"

    - name: Install eslint globally with Bun
      bun_global:
        name: eslint
        version: "9.23.0"
```

If you want, I’ll turn these sketches into collection-ready modules with proper
docs stanzas and a small unit-test matrix.

[1]: <https://docs.astral.sh/uv/guides/tools/> "Using tools | uv" [2]:
<https://docs.astral.sh/uv/reference/cli/> "Commands | uv" [3]:
<https://docs.rs/crate/cargo-binstall/latest> "cargo-binstall 1.17.9 - Docs.rs"
[ 4]: <https://bun.com/docs/guides/install/from-npm-install-to-bun-install>
"Migrate from npm install to bun install - Bun"
