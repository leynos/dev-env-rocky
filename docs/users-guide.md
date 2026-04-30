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
is written to `~/.claude/settings.json`. The roles avoid raw text block edits
for these files and instead use structured Ansible modules so existing
configuration survives repeated runs.

## Firecrawl MCP

The playbook installs the `firecrawl-mcp` package through the global Bun package
role and links the executable into `~/.local/bin/firecrawl-mcp`. Codex is then
configured with this MCP server:

```toml
[mcp_servers.firecrawl]
command = "firecrawl-mcp"

[mcp_servers.firecrawl.env]
FIRECRAWL_API_KEY = "..."
```

The real API key is not stored in plaintext in the repository. The role reads
the vaulted `firecrawl_api_key` variable and writes it into the Codex MCP
environment. The local Vault value is maintained from `~/__firecrawl_token`.

To rotate the Firecrawl key:

1. Write the new token to `~/__firecrawl_token`.
2. Refresh the ignored Vault file `ansible/group_vars/all/vault.yml` with
   `ansible-vault`.
3. Run `make site`, or run a narrower play for the affected host.
4. Verify that `~/.codex/config.toml` contains the `firecrawl` MCP server and
   that `~/.local/bin/firecrawl-mcp` is executable.

## Sccache Environment

The `sccache_user` role writes these environment values for Codex and Claude:

- `RUSTC_WRAPPER`
- `RUSTC_HEARTBEAT_SECS`
- `SCCACHE_DIR`
- `SCCACHE_CACHE_SIZE`

Codex receives the values under the TOML `[env]` table in
`~/.codex/config.toml`. Claude receives the same values under the JSON `env`
object in `~/.claude/settings.json`.

The obsolete `~/.claude/config.toml` file is removed because Claude does not use
that TOML path for these settings.
