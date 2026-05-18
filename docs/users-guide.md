# Users' Guide

This repository provisions development hosts with the tools and agent
configuration used by the owner account. The main entrypoint is the Ansible
site playbook:

```bash
make site
```

Use `make check` when a dry run is needed before changing a host.

## Agent Configuration

The `agent_tools` and `sccache_user` roles configure user-scoped agent files
under the owner user's home directory.

The collection boundary in `docs/adr-002-collection-boundary.md` does not
change the current playbook commands or generated files. It records which parts
of this configuration may later become reusable collection roles and which
parts remain site-local orchestration for the owner's environment.

Codex configuration is written to `~/.codex/config.toml`.
Cursor Model Context Protocol (MCP) configuration is written to
`~/.cursor/mcp.json`, and Cursor skills are installed under
`~/.cursor/skills`. These paths use structured Ansible modules so existing
configuration survives repeated runs.

Claude stop-hook configuration is an exception: `~/.claude/settings.json` is
written by an `agent_tools` shell task that uses `jq` to write the `hooks.Stop`
entry. Environment and `PATH` values in the same file are managed through the
structured `json_file` module in the `sccache_user` role.

DeepSeek-TUI configuration is provided by the reusable
`agentic.agent_configs.deepseek_tui` collection role. The role installs pinned
`deepseek-tui@0.8.24` through Bun, links `deepseek` and `deepseek-tui` into the
owner user's `~/.local/bin`, and writes:

- `~/.deepseek/config.toml`, including DeepSeek provider defaults and feature
  flags for MCP and subagents.
- `~/.deepseek/mcp.json`, using DeepSeek-TUI's native `servers` object.
- `~/.deepseek/skills/<slug>/SKILL.md` and optional support files.

The role also installs the Python packages needed by the TOML-backed Ansible
modules on the managed host. Override `deepseek_tui_mcp_servers`,
`deepseek_tui_hooks`, `deepseek_tui_skills` and `deepseek_tui_config_values` to
add local policy without editing the collection role.

The `cursor_cli` role installs Cursor CLI through the official Linux and WSL
installer:

```bash
curl https://cursor.com/install --retry 3 --connect-timeout 10 -fsS | bash
```

The installer creates the `cursor-agent` binary under `~/.local/bin`. The role
runs before `agent_tools` so Cursor exists before MCPs and skills are
configured. Cursor CLI does not currently support stop hooks, so this
repository does not install Cursor stop-hook configuration.

The `coderabbit_cli` role installs CodeRabbit CLI through the downloaded
installer script vendored inside this repository at
`ansible/roles/coderabbit_cli/files/coderabbit-install.sh`. The upstream source
for that script is:

```text
https://cli.coderabbit.ai/install.sh
```

The role runs the installer with `CODERABBIT_INSTALL_DIR=~/.local/bin`, which
creates both `~/.local/bin/coderabbit` and the short `~/.local/bin/cr` alias.
It then authenticates CodeRabbit CLI with:

```bash
coderabbit auth login --api-key <vaulted-key>
```

The API key comes from the host-keyed `coderabbit_api_keys` mapping in each
host's source-of-truth vault file at `ansible/host_vars/<hostname>/vault.yml`,
for example `ansible/host_vars/rohga.df12.net/vault.yml`, and the role
suppresses task output while the secret is in use.

To rotate a host's CodeRabbit API key:

1. Write the replacement token to the matching local token file:
   `~/__coderabbit_token_rohga` for `rohga.df12.net` or
   `~/__coderabbit_token_vendetta` for `vendetta.df12.net`.
2. Update the `coderabbit_api_keys.<host>` value in
   `ansible/host_vars/<hostname>/vault.yml`, for example
   `ansible/host_vars/rohga.df12.net/vault.yml`, and re-encrypt that file with
   `~/.ansible_vault_pass`.
3. Remove `~/.coderabbit/auth.json` on the affected host if CodeRabbit CLI has
   already been authenticated with the old key.
4. Run `make site`, or run a narrower play for the affected host.
5. Verify that `coderabbit review --agent` runs from a git repository as the
   owner user.

The role fails with installer stdout and stderr when installation does not
create the expected `coderabbit` executable and `cr` alias. Common remediation
steps are to ensure the managed host has `git` and `unzip`, check network
access to the configured CodeRabbit release URL, and remove
`~/.local/bin/coderabbit` only when a forced reinstall is required.

Ansible runs the role sequentially for each host connection. Parallel
multi-host playbook execution remains isolated because every host writes under
that host's owner-user home directory. The installer uses a private `mktemp`
directory for downloads, so playbook-managed installation is safe across hosts;
running the installer directly in concurrent shells for the same user is not a
supported workflow.

## Login Shell PATH

The `paths` role writes `~/.bashrc.d/00-paths` and appends managed source hooks
to `~/.bashrc` and `~/.bash_profile`. Login shells therefore normalize
duplicate managed entries and keep user-local commands ahead of package-manager
shims:

```text
PATH=$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.bun/bin:$HOME/go/bin:...
```

## Lody Daemon PATH

When `lody` is enabled, `agent_tools` writes
`~/.config/systemd/user/lody-daemon.service` with a fixed service `PATH`
environment so the daemon is not dependent on shell startup files such as
`~/.bashrc`.

```text
PATH=$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.bun/bin:$HOME/go/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin
```

## System Packages

The `packages` role provisions RPM packages on the managed host. The full list
is maintained in `ansible/roles/packages/tasks/main.yml`; add new packages
there.

The following packages are currently provisioned:

- `ninja-build` — provides the `ninja` binary, required when projects use
  Ninja as their build backend (e.g. Meson, or CMake configured with
  `-G Ninja`).
- `htop` — provides an interactive process viewer for inspecting CPU, memory,
  and process state on managed hosts.
- `unzip` — extracts CodeRabbit CLI release archives during installation.


## Python Tools

The `uv_tools` role installs user-scoped Python command-line tools with `uv`.
The tools are installed under the managed user's uv tool directory and expose
their commands through the user's normal shell `PATH`.

The following Ansible tools are available after the playbook runs:

- `ansible` — runs ad hoc Ansible commands and links the `ansible-core`
  executables, including `ansible-playbook`, for local playbook workflows.
- `molecule` — runs role scenario tests for local role validation, including
  the Podman Molecule driver plugin.
- `ansible-lint` — checks playbooks and roles for Ansible best practices.

The same role also installs the repository's other Python developer tools, such
as `ruff`, `pyrefly`, `ty`, `yamllint`, `copier`, `mbake`, `basedpyright`,
`repomix`, `python-slugify`, `git-donkey`, `nixie`, and `lading`.

## Factory Droid DeepSeek Models

When Droid is enabled, the playbook configures two Factory Droid custom models:

- `deepseek-v4-pro[1m]`
- `deepseek-v4-pro`

Both models use DeepSeek's Anthropic-compatible endpoint:

```text
https://api.deepseek.com/anthropic
```

The API token is not stored in plaintext in the repository. The role reads the
vaulted `deepseek_api_key` variable and writes it into Factory Droid's
`~/.factory/settings.json` custom model configuration.

## Firecrawl MCP

The playbook installs the `firecrawl-mcp` package through the global Bun
package role and links the executable into `~/.local/bin/firecrawl-mcp`. Codex
and Cursor are then configured with this MCP server.

Codex receives:

```toml
[mcp_servers.firecrawl]
command = "firecrawl-mcp"

[mcp_servers.firecrawl.env]
FIRECRAWL_API_KEY = "..."
```

Cursor receives:

```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "firecrawl-mcp",
      "env": {
        "FIRECRAWL_API_KEY": "..."
      }
    }
  }
}
```

The real API key is not stored in plaintext in the repository. The role reads
the vaulted `firecrawl_api_key` variable and writes it into the Codex and
Cursor MCP environments. The local Vault value is maintained from
`~/__firecrawl_token`.

To rotate the Firecrawl key:

1. Write the new token to `~/__firecrawl_token`.
2. Refresh the ignored Vault file `ansible/group_vars/all/vault.yml` with
   `ansible-vault`.
3. Run `make site`, or run a narrower play for the affected host.
4. Verify that `~/.codex/config.toml` and `~/.cursor/mcp.json` contain the
   `firecrawl` MCP server and that `~/.local/bin/firecrawl-mcp` is executable.

## css-view

The `node_packages` role installs `css-view` globally from the Leynos GitHub
repository through Bun. The package is pinned to a repository commit and trusts
its post-install script so Playwright downloads the browser binaries needed by
the command, including Chromium.

Run `css-view` from the managed shell PATH:

```bash
css-view https://example.org --browser chromium --pretty
```

## Sccache Environment

The `sccache_user` role writes these environment values for Codex and Claude:

- `RUSTC_WRAPPER`
- `RUSTC_HEARTBEAT_SECS`
- `SCCACHE_DIR`
- `SCCACHE_CACHE_SIZE`

Codex receives the values under the TOML `[env]` table in
`~/.codex/config.toml`. Claude receives the same values under the JSON `env`
object in `~/.claude/settings.json`.

Claude also receives a scoped `PATH` value in `~/.claude/settings.json` so
stop-hook commands can find user-installed tools without changing Codex or the
system environment. The role builds the user-owned path entries from the
managed user's home directory and includes `~/.cargo/bin`, `~/.local/bin`, and
`~/.bun/bin`.

The obsolete `~/.claude/config.toml` file is removed because Claude does not
use that TOML path for these settings.
