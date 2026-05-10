# ADR-002: Collection boundary

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

The repository currently contains both reusable Ansible automation and
site-local orchestration for the owner's development hosts. The reusable
surfaces are already visible as two collection directories:

- `agentic.agent_configs`, which manages agent configuration files for Codex
  CLI, Claude Code, Cursor CLI, Factory Droid, JSON, and TOML.
- `packaging.tools`, which manages package-manager operations for Bun, uv, and
  `cargo-binstall`.

The site playbook in `ansible/site.yml` still owns the sequence that turns a
Rocky Linux host into the owner's working environment. That sequence includes
real inventory assumptions, owner-user paths, private repository access,
vaulted secrets, package selections, symlinks, and systemd user services.

Roadmap item 1.1.1 needs a stable boundary before later roadmap work moves role
tasks into collections. Without that boundary, extracting a broad role such as
`agent_tools` would risk creating a Bumpy Road: a large relocation with several
unrelated concerns, hard-to-review responsibilities, and hidden site-specific
assumptions. The safer path is to extract small vertical slices only after
their inputs, outputs, and validation have been made explicit.

## Decision

Reusable collection code owns behaviour that is independent of this
repository's private inventory and can be driven by documented variables. A
collection role or module must be usable without the owner's hostnames, Vault
files, SSH keys, private repositories, or preferred package profile.

Site-local orchestration owns the concrete managed-host profile. It decides
which reusable modules or future collection roles are called, which packages
are installed by default, which private repositories are cloned, which vaulted
secrets are passed, which services are enabled, and where owner-user files are
written.

The collection boundary is:

- `agentic.agent_configs` owns reusable agent configuration primitives. This
  includes modules and future roles for structured JSON/TOML edits, agent MCP
  registration, skills, hooks, subagents, droids, and custom models, provided
  those roles accept all site-specific inputs as variables.
- `packaging.tools` owns reusable package-management primitives. This includes
  Bun, uv, `cargo-binstall`, and future roles that install configurable package
  sets without embedding this repository's default host profile.
- The site playbook owns host orchestration. It composes system roles,
  user-environment roles, collection modules, secrets, private repository
  choices, and enablement flags into the current development-host behaviour.

The extraction candidates are classified as follows:

- `agent_tools`: site-local. The current role mixes private repository cloning,
  SSH key lifecycle, vaulted API keys, client-specific MCP registration, hooks,
  Factory Droid custom models, helper executables, and user services. Later
  roadmap phases may extract individual agent configuration slices into
  `agentic.agent_configs`, but the current role is not moved as one unit.
- `packages`: extract-later. CRB enablement, EPEL setup, and the selected RPM
  list are currently the site's default Rocky Linux profile. A future
  `packaging.tools` role may own this once package groups, overrides, and
  host-profile tests are documented.
- `infra_tools`: extract-later. The role installs infrastructure tools and
  upstream repositories that could become reusable, but the installer inputs,
  version policy, repository trust, and validation contract are not yet
  explicit enough for collection ownership.
- `rust_crates`: extract-later. The role uses package-manager primitives that
  fit `packaging.tools`, but the bootstrap path, crate list, install root, and
  version-pinning contract still need a role variable convention.
- `uv_tools`: extract-later. The role already delegates installation to a
  package module, but the chosen Python tool list and Git-backed specs are
  still fixed site policy rather than a reusable role interface.
- `node_packages`: extract-later. The role has Molecule coverage and uses a
  reusable Bun module, but the enabled package set, trusted post-install
  policy, symlinks, and optional browser tooling remain site-profile choices
  until a variable contract is recorded.

The current `agentic.agent_configs` modules and `packaging.tools` modules are
extract-now surfaces because they already have collection metadata, narrow
module contracts, and unit tests. Duplicated package modules under
`agentic.agent_configs` should be treated as a cleanup target, not as shared
ownership of package-manager behaviour.

## Consequences

- Later roadmap tasks must not move a local role wholesale just because it
  calls reusable modules. They should extract one responsibility at a time
  after documenting variables, defaults, secrets, and validation.
- Extracted roles must preserve current `make site` and `make check` behaviour
  until a later decision deliberately changes the managed-host profile.
- Site-local roles may remain as wrappers around collection roles when they
  carry owner-specific defaults, private repository definitions, vaulted secret
  names, or host enablement policy.
- The developers' guide should point contributors to this ADR when deciding
  whether a change belongs in a collection or in site-local orchestration.
- The users' guide should continue to describe observable playbook behaviour,
  not internal extraction mechanics, unless a collection change alters what a
  user runs or verifies.
