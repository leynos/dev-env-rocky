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

Codex configuration is written to `~/.codex/config.toml`. Cursor MCP
configuration is written to `~/.cursor/mcp.json`, and Cursor skills are
installed under `~/.cursor/skills`. These paths use structured Ansible modules
so existing configuration survives repeated runs.

Claude stop-hook configuration is an exception: `~/.claude/settings.json` is
written by an `agent_tools` shell task that uses `jq` to write the `hooks.Stop`
entry. Environment and `PATH` values in the same file are managed through the
structured `json_file` module in the `sccache_user` role.

The `cursor_cli` role installs Cursor CLI through the official Linux and WSL
installer:

```bash
curl https://cursor.com/install --retry 3 --connect-timeout 10 -fsS | bash
```

The installer creates the `cursor-agent` binary under `~/.local/bin`. The role runs
before `agent_tools` so Cursor exists before MCPs and skills are configured.
Cursor CLI does not currently support stop hooks, so this repository does not
install Cursor stop-hook configuration.

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
