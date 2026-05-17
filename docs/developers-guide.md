# Developers' Guide

This guide documents the local design rules for the agent configuration modules
and the roles that use them.

## Collection Boundary

`docs/adr-002-collection-boundary.md` records the accepted boundary between
reusable Ansible collections and site-local orchestration.

Use `agentic.agent_configs` for reusable agent configuration primitives:
structured JSON/TOML edits, agent MCP registration, skills, hooks, subagents,
droids, and custom models. Use `packaging.tools` for reusable package-manager
primitives and future configurable package roles. Keep site-local roles as the
owner of the concrete managed-host profile: private repositories, vaulted
secret variable names, package selections, symlinks, service enablement,
inventory assumptions, and owner-user policy.

Do not move a whole local role into a collection simply because it calls
collection modules. Extract one responsibility only after its inputs, defaults,
secrets, and validation are documented. Until that contract exists, the role is
site-local orchestration.

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

The `agent_tools` role installs helper executables into `~/.local/bin`,
including `markdownlint`, `mdformat-all`, and `notdeadyet`. That directory must
be created before any copy task writes those helpers, otherwise a fresh managed
host can fail before later roles have had a chance to create the user-local
binary path.

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
the previous file snapshots, so the two surfaces do not remain partially
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

The `cursor_cli` Ansible role installs the Cursor `cursor-agent` binary from
the official Linux and WSL installer script. The role is idempotent: the shell
task declares `creates: ~/.local/bin/cursor-agent`, so the installer runs only
when the binary is absent.

The role must appear before `agent_tools` in `site.yml`. This ordering ensures
the `cursor-agent` binary exists before `agent_tools` configures Cursor MCP
servers and skills.


## uv_tools Role

The `uv_tools` role installs user-scoped Python CLIs through
`packaging.tools.uv_tool`. It first ensures `uv` is available, then loops over
the required tools with the explicit `uv_path` set to
`{{ ansible_env.HOME }}/.local/bin/uv`.

The role installs Ansible workflow tools:

- `ansible`, for ad hoc Ansible commands and Python package availability;
- `molecule`, with `molecule-plugins[podman]`, for local role scenario tests
  that use the Podman driver;
- `ansible-lint`, for playbook and role linting.

It also installs the broader Python tooling used by this repository and the
managed host workflow:

- `ruff`, for Python formatting and linting;
- `pyrefly`, `ty`, and `basedpyright`, for Python type checking;
- `yamllint`, for YAML linting;
- `copier`, for project templating;
- `mbake`, for Makefile validation;
- `repomix`, for repository packaging;
- `python-slugify`, for slug generation;
- `git-donkey`, `nixie`, and `lading`, from their Leynos Git repositories.

## CodeRabbit CLI Role

The `coderabbit_cli` Ansible role installs the CodeRabbit `coderabbit` binary
and the `cr` alias into the managed user's `~/.local/bin` directory. The role
copies the checked-in installer from
`ansible/roles/coderabbit_cli/files/coderabbit-install.sh` instead of curling
the installer during the play. The copied installer is executed with
`CODERABBIT_INSTALL_DIR` set to the managed user-local bin directory and with
`creates: ~/.local/bin/coderabbit`, so the installation task is idempotent
after the binary exists.

The role authenticates the CLI by running `coderabbit auth login --api-key`
with the host's entry in the vaulted `coderabbit_api_keys` mapping. That
command task must keep `no_log: true` because the argv contains a secret. The
task uses `creates: ~/.coderabbit/auth.json` so an already-authenticated CLI is
not re-authenticated on every playbook run.

The role has a Molecule `rocky10` scenario. The scenario installs the
installer's RPM prerequisites, builds a local fake CodeRabbit release archive
under `/tmp/coderabbit-releases`, points `CODERABBIT_DOWNLOAD_URL` at that
fixture, and verifies the installed binary, `cr` symlink, auth file, agent
review mode, installer output, permissions, ownership, and idempotence. This
keeps the e2e test deterministic and does not depend on CodeRabbit's public
release service.

Installer failures should remain observable without exposing secrets. The
installation task captures stdout and stderr, validates the expected binary and
alias after the installer exits, and reports those streams through a rescue
failure message. Authentication remains a separate `no_log: true` task because
its argv contains the vaulted API key.

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

## Tool Package Modules

The `packaging.tools` collection provides thin wrappers around three package
manager CLIs. Each module follows the same narrow contract:
`state: present|absent`, an optional exact `version`, check mode, and modest
return data (`name`, `state`, `previous_version`, `installed_version`, `cmd`).

### uv_tool

`packaging.tools.uv_tool` installs and removes Python tools managed by `uv`.

Key parameters:

- `name` (required): Tool name as reported by `uv tool list`.
- `version`: Exact version to install.
- `spec`: Full install specifier; overrides the `name==version` default.
- `with_packages`: Additional packages to include via `--with`.
- `python`: Python version or path passed to `--python`.
- `force`: Pass `--force` to reinstall even if already present.
- `uv_path`: Path to the `uv` executable; defaults to `uv`.

State detection reads `uv tool list`. That output is human-oriented and has no
documented stable machine-readable contract, so the regex parser may need
adjustment if `uv` changes its output layout. The `name` parameter must match
what `uv tool list` reports, which is the package name — not the executable
name.

### cargo_binstall

`packaging.tools.cargo_binstall` installs and removes Rust binaries via
`cargo-binstall`.

Key parameters:

- `name` (required): Crate name.
- `version`: Exact version; install target becomes `name@version`.
- `root`: Sets `CARGO_INSTALL_ROOT`; must be passed to both install and
  uninstall operations.
- `no_confirm`: Pass `--no-confirm`; defaults to `true` for unattended runs.
- `force`: Pass `--force` to reinstall.
- `cargo_path`: Path to the `cargo` executable; defaults to `cargo`.

State detection uses `cargo install --list`, which is documented and stable.
Removal uses `cargo uninstall`. The assumption that `cargo-binstall` writes
entries readable by `cargo install --list` is reasonable given binstall's
stated goal of being a drop-in for `cargo install`, but is an inference rather
than an explicit compatibility guarantee.

### bun_global

`packaging.tools.bun_global` installs and removes global Node packages via Bun.

The `node_packages` role keeps trusted lifecycle-script execution explicit. Any
package with `trust_postinstall: true` must include a
`trust_postinstall_reason` entry and an exact `version` pin in the same loop
item. Optional packages that trust postinstall scripts, such as `puppeteer` and
`@zed-industries/codex-acp-linux-x64`, are disabled by role defaults and
enabled by host profile variables only where needed. The ACP extension is
additionally restricted to Linux x86_64 hosts.

Key parameters:

- `name` (required): Package name, including scoped names such as
  `@scope/pkg`.
- `version`: Exact version; install target becomes `name@version`.
- `global_dir`: Override for the global modules directory; defaults to
  `$BUN_INSTALL_GLOBAL_DIR` or `~/.bun/install/global`.
- `global_bin_dir`: Override for the global bin directory; defaults to
  `$BUN_INSTALL_BIN` or `~/.bun/bin`.
- `ignore_scripts`: Pass `--ignore-scripts` to suppress lifecycle scripts.
- `bun_path`: Path to the `bun` executable; defaults to `bun`.

State detection reads `package.json` from the global `node_modules` tree. If
`install.globalDir` is set in `bunfig.toml` without exporting the matching
environment variable, pass `global_dir` explicitly, so the module reads the
correct location.

### Playbook example

```yaml
- hosts: all
  tasks:
    - name: Install ruff with uv
      packaging.tools.uv_tool:
        name: ruff
        version: "0.5.0"

    - name: Install cargo-nextest with cargo-binstall
      packaging.tools.cargo_binstall:
        name: cargo-nextest
        version: "0.9.86"

    - name: Install eslint globally with Bun
      packaging.tools.bun_global:
        name: eslint
        version: "9.23.0"
```

## Dependencies

Managed hosts are expected to run Rocky Linux 10 or newer with system Python
3.12 or newer. Additional dependencies introduced by the agent configuration
work are:

- `python3-tomlkit`, installed by the package role for TOML round-trip writes;
- `ansible`, `molecule`, and `ansible-lint`, installed by the `uv_tools` role
  for Ansible command execution, role scenario testing, and linting;
- `firecrawl-mcp`, installed globally through Bun for Codex MCP access;
- `ninja-build`, installed by the `packages` role to provide the `ninja`
  binary for projects that use Ninja as their build backend;
- `htop`, installed by the `packages` role to provide an interactive process
  viewer for inspecting CPU, memory, and process state.

## Validation

Before committing changes to these roles or modules, run:

```bash
make check-fmt
make lint
make typecheck
make test
make check
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

Run the Molecule role scenarios when editing role behaviour that depends on the
managed host shell or package-install environment:

```bash
MOLECULE='uv run --with ansible-core --with molecule --with molecule-plugins[podman] molecule' \
make molecule
```

The Molecule scenarios use Podman with the `quay.io/rockylinux/rockylinux:10`
image. They cover the `uv_tools` role's uv install loop with a fake uv fixture,
including executable PATH checks for Ansible workflow tools and the
`molecule-plugins[podman]` dependency for Molecule's Podman driver; the
`node_packages` role's Bun global install flow with a fake Bun fixture,
including trusted postinstall handling for `css-view`; and the `paths` role's
managed PATH precedence for login shells.
