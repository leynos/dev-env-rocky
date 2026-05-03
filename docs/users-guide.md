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

Codex configuration is written to `~/.codex/config.toml`. Claude configuration
is written to `~/.claude/settings.json`. Cursor MCP configuration is written to
`~/.cursor/mcp.json`, and Cursor skills are installed under `~/.cursor/skills`.
The roles avoid raw text block edits for these files and instead use structured
Ansible modules so existing configuration survives repeated runs.

The `cursor_cli` role installs Cursor CLI through the official Linux and WSL
installer:

```bash
curl https://cursor.com/install -fsS | bash
```

The installer creates the `agent` binary under `~/.local/bin`. The role runs
before `agent_tools` so Cursor exists before MCPs and skills are configured.
Cursor CLI does not currently support stop hooks, so this repository does not
install Cursor stop-hook configuration.

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
