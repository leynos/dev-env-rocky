# Developers' Guide

This guide documents the local design rules for the agent configuration modules
and the roles that use them.

## Structured File Modules

The `agentic.agent_configs` collection includes generic modules for structured
configuration updates:

- `json_file` manages a nested value inside a JSON object file.
- `toml_file` manages a nested value inside a TOML file using `tomlkit`.

Both modules accept a dot-separated `key`, for example
`env.RUSTC_WRAPPER`. Literal dots can be escaped with a backslash. The modules
create missing parent objects or tables, preserve unrelated configuration, and
support `state: present` and `state: absent`.

Use these modules instead of `ansible.builtin.blockinfile` when changing agent
configuration files. Text blocks are fragile for JSON and TOML because they can
produce invalid syntax, duplicate tables, or overwrite user-managed settings.

## Codex Subagents

`codex_cli_subagent` manages two coordinated Codex surfaces:

- a subagent TOML file under `~/.codex/agents` or `.codex/agents`;
- a registry entry under `[agents.<slug>]` in the matching `config.toml`.

The module validates the subagent and registry data before writing. When a
registry update fails after the subagent file has changed, the module restores
the previous file snapshots so the two surfaces do not remain partially
updated.

## Firecrawl MCP

The Firecrawl MCP integration is split across two roles:

- `node_packages` installs the `firecrawl-mcp` Bun package and links
  `~/.local/bin/firecrawl-mcp` to the Bun global executable.
- `agent_tools` registers the Codex MCP server and passes
  `FIRECRAWL_API_KEY` from the vaulted `firecrawl_api_key` variable.

The Firecrawl task uses `no_log: true` because the MCP environment contains a
secret. Tests assert this on the Firecrawl task block itself, not by searching
the whole role file.

## Dependencies

Managed hosts are expected to run Rocky Linux 10 or newer with system
Python 3.12 or newer. Additional dependencies introduced by the agent
configuration work are:

- `python3-tomlkit`, installed by the package role for TOML round-trip writes;
- `firecrawl-mcp`, installed globally through Bun for Codex MCP access.

## Validation

Before committing changes to these roles or modules, run:

```bash
make check-fmt
make lint
make typecheck
make test
make markdownlint
git diff --check
PACKAGING_MODULES=./ansible/ansible_collections/packaging/tools/plugins/modules
AGENT_MODULES=./ansible/ansible_collections/agentic/agent_configs/plugins/modules
ANSIBLE_CONFIG=./ansible/ansible.cfg \
ANSIBLE_COLLECTIONS_PATH=./ansible/ansible_collections \
ANSIBLE_LIBRARY="${PACKAGING_MODULES}:${AGENT_MODULES}" \
ANSIBLE_MODULE_UTILS=./ansible/ansible_collections/agentic/agent_configs/plugins/module_utils \
ansible-playbook -i ansible/inventory.ini ansible/site.yml --syntax-check
```

Run focused collection tests when editing custom modules:

```bash
PYTHONPATH=ansible UV_CACHE_DIR=.uv-cache \
uv run --with pytest --with 'ansible-core==2.18.6' --with tomlkit \
pytest -q \
  ansible/ansible_collections/agentic/agent_configs/tests/unit/plugins/modules/test_agent_config_modules.py
```
