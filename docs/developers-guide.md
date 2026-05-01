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

## Module Utilities API

Module authors should use the shared helpers in `agent_config_common.py` rather
than reimplementing file, path, or registry handling inside individual modules.
The expected public helpers are:

- `log_operation`, for structured Ansible log messages at important decisions;
- `atomic_write_text`, for replacing UTF-8 text files without partial writes;
- `expand_path`, for normalising user-provided paths before file access;
- `read_text`, for optional UTF-8 reads where missing files are acceptable;
- `fail_with_io_error`, for normalising and raising consistent I/O errors;
- `write_text_if_changed`, for idempotent text writes with check-mode support;
- `write_toml_if_changed`, for idempotent TOML writes with `tomlkit`;
- `manage_named_toml_entry`, for named registry entries in TOML tables;
- `manage_named_json_entry`, for named registry entries in JSON objects;
- `resolve_relative_config_file`, for Codex subagent `config_file` values;
- `resolve_scoped_config_path`, for user, project, and local config paths.

Use `pathlib.Path` for new path manipulation in module utility helpers. The
explicit `Path` operations make relative path handling, parent lookup, and
cross-platform path semantics easier to review than equivalent `os.path`
chains.

The `agent_tools` role installs two helper executables into `~/.local/bin`:
`mdformat-all` and `notdeadyet`. That directory must be created before any
copy task writes those helpers, otherwise a fresh managed host can fail before
later roles have had a chance to create the user-local binary path.

`codex_cli_subagent` coordinates a subagent TOML file and its registry entry in
`config.toml`. If a registry write fails after the subagent file has changed,
catch only the Ansible failure shape produced by `fail_json`, restore both the
subagent file and registry file snapshots with `restore_snapshot`, then fail
the module. Re-raise all other exceptions so unexpected defects surface during
testing instead of being converted into ordinary Ansible validation failures.

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
