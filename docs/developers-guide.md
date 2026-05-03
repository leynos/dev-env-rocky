# Developers' Guide

This guide documents the local design rules for the agent configuration modules
and the roles that use them.

## Structured File Modules

The `agentic.agent_configs` collection includes generic modules for structured
configuration updates:

- `json_file` manages a nested value inside a JSON object file.
- `toml_file` manages a nested value inside a TOML file using `tomlkit`.

Both modules accept a dot-separated `key`, for example `env.RUSTC_WRAPPER`.
Literal dots can be escaped with a backslash. The modules create missing parent
objects or tables, preserve unrelated configuration, and support
`state: present` and `state: absent`.

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
cross-platform path semantics easier to review than equivalent `os.path` chains.

The `agent_tools` role installs two helper executables into `~/.local/bin`:
`mdformat-all` and `notdeadyet`. That directory must be created before any copy
task writes those helpers, otherwise a fresh managed host can fail before later
roles have had a chance to create the user-local binary path.

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
the previous file snapshots so the two surfaces do not remain partially updated.

## Firecrawl MCP

The Firecrawl MCP integration is split across two roles:

- `node_packages` installs the `firecrawl-mcp` Bun package and links
  `~/.local/bin/firecrawl-mcp` to the Bun global executable.
- `agent_tools` registers the Codex MCP server and passes
  `FIRECRAWL_API_KEY` from the vaulted `firecrawl_api_key` variable.

The Firecrawl task uses `no_log: true` because the MCP environment contains a
secret. Tests assert this on the Firecrawl task block itself, not by searching
the whole role file.

## Factory Droid Custom Models

`factory_droid_model` manages one entry in Factory Droid's `customModels` list
inside `~/.factory/settings.json`. Entries are keyed by the provider model ID,
which lets the module update or remove one custom model without replacing other
user-managed models.

The `agent_tools` role uses this module to configure the DeepSeek Anthropic API
endpoint at `https://api.deepseek.com/anthropic` for `deepseek-v4-pro[1m]` and
`deepseek-v4-pro`. The API token comes from the vaulted `deepseek_api_key`
variable, and the task must keep `no_log: true` because the rendered model
entry contains the token.

## Cursor CLI Role

The `cursor_cli` Ansible role installs the Cursor `agent` binary from the
official Linux and WSL installer script. The role is idempotent: the shell task
declares `creates: ~/.local/bin/agent`, so the installer runs only when the
binary is absent.

The role must appear before `agent_tools` in `site.yml`. This ordering ensures
the `agent` binary exists before `agent_tools` configures Cursor MCP servers
and skills.

## cursor_cli_mcp Module

`agentic.agent_configs.cursor_cli_mcp` manages `mcpServers` entries in
`~/.cursor/mcp.json` (user scope) or `.cursor/mcp.json` (project scope). Cursor
CLI discovers the same MCP configuration as the editor, so the same file serves
both surfaces.

Key parameters:

- `name` (required): MCP server name used as the dict key.
- `state`: `present` or `absent`.
- `scope`: `user` (default) or `project`.
- `transport`: `stdio`, `http`, or `sse`.
- `command`/`url`: executable path for stdio servers or URL for http/sse.

The `env` and `headers` keys are redacted in the returned `server` result to
prevent secrets from appearing in Ansible task output. The values written to
`mcp.json` are unaffected.

## cursor_cli_skill Module

`agentic.agent_configs.cursor_cli_skill` manages skill directories under
`~/.cursor/skills/<slug>` (user scope) or `.cursor/skills/<slug>` (project
scope). Each directory contains a `SKILL.md` file with YAML front matter and
optional extra files.

Key parameters:

- `name` (required): Skill display name.
- `slug`: Directory name, derived from `name` when omitted.
- `description`: Skill description written to front matter.
- `body`: Markdown body for `SKILL.md`.
- `scope`: `user` (default) or `project`.

## CheckModeToml Adapter

`CheckModeToml` is a class in `toml_file.py` that provides a `tomlkit`
-compatible API backed by the standard-library `tomllib`. It is returned by
`import_tomlkit()` when `tomlkit` is not installed and `check_mode=True`.

This allows `toml_file` to report would-change outcomes during dry runs on
hosts where `python3-tomlkit` has not yet been installed. Because `tomllib` is
read-only, `CheckModeToml.parse()` works for reads but writes are not performed
in check mode anyway.

## strip_legacy_sccache_env_block() Helper

`strip_legacy_sccache_env_block(content)` is a helper in
`agent_config_common.py` that removes the obsolete
`# BEGIN ANSIBLE MANAGED BLOCK - sccache env` TOML block written by earlier
versions of this repository. That block duplicated the top-level `[env]` table
and caused TOML parse errors.

Signature: `strip_legacy_sccache_env_block(content: str) -> tuple[str, bool]`

Returns `(cleaned_content, was_changed)`. It is called automatically by
`load_toml_file()` and by `toml_file`'s `load_document()` before parsing, so
callers do not need to invoke it directly.

## Dependencies

Managed hosts are expected to run Rocky Linux 10 or newer with system Python
3.12 or newer. Additional dependencies introduced by the agent configuration
work are:

- `python3-tomlkit`, installed by the package role for TOML round-trip writes;
- `firecrawl-mcp`, installed globally through Bun for Codex MCP access;
- `ninja-build`, installed by the `packages` role to provide the `ninja`
  binary for projects that use Ninja as their build backend.

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
