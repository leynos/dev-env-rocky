# Dev environment Rocky roadmap

This roadmap translates the current Ansible role extraction findings into an
outcome-oriented delivery sequence. It does not promise dates. Each phase
carries one testable idea at the Goal, Idea, Steps, and Tasks (GIST) level.
The steps underneath that phase work toward validating or falsifying the idea,
answering sequencing questions,
and leaving behind usable automation rather than another horizontal layer.

The roadmap is grounded in the existing operator and developer documentation,
the site playbook role boundaries, and the current collection/module testing
shape. The primary source documents are `docs/users-guide.md`,
`docs/developers-guide.md`, `docs/documentation-style-guide.md`,
`ansible/site.yml`, the roles under `ansible/roles/`, and the collection tests
under `ansible/ansible_collections/`.

## 1. Foundational extraction contracts

Idea: if the repository records the role-collection boundary, variable
contract, and validation spine before moving tasks, later extraction slices can
improve configurability without changing the provisioned host behaviour.

This phase settles what belongs in a reusable collection and what remains
site-local. It also creates the test scaffolding that each extracted role must
pass before the playbook can switch from local roles to collection roles.

### 1.1. Record the role-collection boundary

This step answers which responsibilities are reusable collection behaviour and
which are specific to the owner's environment. The outcome informs the order of
role moves and prevents a broad relocation of `agent_tools` without a stable
contract. See `docs/developers-guide.md` §§Structured File Modules-Validation,
`docs/users-guide.md` §§Agent Configuration-Firecrawl Model Context Protocol
(MCP), and
`ansible/site.yml` §§1-54.

- [ ] 1.1.1. Add an architectural decision record for the collection boundary.
  - Define the boundary between `agentic.agent_configs`,
    `packaging.tools`, and site-local orchestration.
  - Classify `agent_tools`, `packages`, `infra_tools`, `rust_crates`,
    `uv_tools`, and `node_packages` as extract-now, extract-later, or
    site-local.
  - Success: one accepted decision identifies collection ownership for each
    extraction candidate.
- [ ] 1.1.2. Document the compatibility rule for extracted roles.
  - Requires 1.1.1.
  - State that extracted roles must preserve the `make site` and `make check`
    behaviour documented in `docs/users-guide.md` and `Makefile` §§31-43.
  - Success: later tasks have a written rule for when the playbook may switch
    from a local role to a collection role.
- [ ] 1.1.3. Add a role variable contract convention.
  - Requires 1.1.1.
  - Define where defaults, argument specs, required secrets, and feature flags
    live for extracted roles.
  - Success: new collection roles have a documented place for configurable
    package lists, agent clients, repositories, models, and service settings.

### 1.2. Establish role-level validation scaffolding

This step answers whether extracted roles can be tested directly instead of
only through static YAML assertions and full-playbook runs. The outcome informs
how aggressively later phases can split tasks. See `Makefile` §§50-70 and
`docs/developers-guide.md` §Validation.

- [ ] 1.2.1. Add a focused role-test harness for collection roles.
  - Requires 1.1.2 and 1.1.3.
  - Choose the local test runner pattern for role execution, check mode,
    idempotence, and argument-spec validation.
  - Success: one trivial collection role can be executed in isolation by the
    same gate family as the existing `make test` target.
- [ ] 1.2.2. Preserve the current static role regression tests as migration
  guards.
  - Requires 1.2.1.
  - Keep the existing task-name and content assertions until each extracted
    role has direct role execution coverage.
  - Success: static tests fail if a role switch drops known tasks before the
    equivalent collection coverage exists.
- [ ] 1.2.3. Add documentation for the extraction gate sequence.
  - Requires 1.2.1.
  - Extend `docs/developers-guide.md` with the exact commands for collection
    role tests, focused module tests, `make check`, and Markdown validation.
  - Success: a contributor can validate an extracted role without reading the
    full playbook.

## 2. Agent tooling as reusable agent configuration

Idea: if `agent_tools` can be split into reusable agent configuration roles
without changing Codex, Claude, Cursor, or Factory Droid outputs, the largest
coupling point becomes testable and the existing custom modules gain clearer
operational contracts.

This phase delivers the highest-value extraction first. It keeps each vertical
slice tied to a real agent surface so the work proves behaviour end to end:
repository inputs, installed skills, structured MCP configuration, hooks,
models, and user services.

### 2.1. Extract agent source repositories and skill distribution

This step answers whether skill source checkout and skill installation can be
configured as data instead of duplicated copy blocks. The outcome informs the
later MCP and hook roles because those roles depend on the same source
repositories. See `ansible/roles/agent_tools/tasks/main.yml` §§4-382 and
`docs/users-guide.md` §Agent Configuration.

- [ ] 2.1.1. Create an `agentic.agent_configs` role for agent skill sources.
  - Requires steps 1.1-1.2.
  - Move public and private skill repository checkout into a collection role
    with configurable repository definitions, destination paths, key file, and
    private-repository gating.
  - Success: the role can clone the existing skill sources and still produces
    the same `~/git/*` layout used by `agent_tools`.
- [ ] 2.1.2. Create an `agentic.agent_configs` role for skill installation.
  - Requires 2.1.1.
  - Configure target clients as data for Codex, Claude, Cursor, and Factory
    Droid instead of repeating one copy loop per source and client.
  - Success: the role installs the same skill directories under `.codex`,
    `.claude`, `.cursor`, and `.factory` with client enablement controlled by
    variables.
- [ ] 2.1.3. Switch the site playbook to the extracted skill roles.
  - Requires 2.1.1 and 2.1.2.
  - Keep the local `agent_tools` role as the owner of MCPs, hooks, models, and
    services until their slices land.
  - Success: `make check` shows no loss of skill installation tasks for
    enabled clients.

### 2.2. Extract MCP registration for agent clients

This step answers whether shared MCP server definitions can configure all
supported agent clients through collection roles without duplicating
`context_pack`, Playwright, and Firecrawl definitions. The outcome informs how
future MCP additions are reviewed. See
`ansible/roles/agent_tools/tasks/main.yml` §§404-462 and §§615-727 and
`docs/users-guide.md` §Firecrawl MCP.

- [ ] 2.2.1. Create a reusable MCP definition contract.
  - Requires 2.1.3.
  - Define the common MCP data shape for `context_pack`, Playwright, and
    Firecrawl, including secret-bearing environment values.
  - Success: one variable list can drive Codex, Claude, Cursor, and Factory
    Droid MCP registration.
- [ ] 2.2.2. Add an `agentic.agent_configs` role for MCP registration.
  - Requires 2.2.1.
  - Use the existing `codex_cli_mcp`, `claude_code_mcp`, `cursor_cli_mcp`, and
    `factory_droid_mcp` modules behind a role-level client matrix.
  - Success: Firecrawl remains `no_log: true`, and generated client
    configuration is unchanged for existing hosts.
- [ ] 2.2.3. Replace local MCP tasks with the collection role.
  - Requires 2.2.2.
  - Remove only the duplicated local MCP task blocks that are covered by the
    new role tests.
  - Success: focused tests confirm Codex, Claude, Cursor, and Factory Droid
    receive the expected MCP entries.

### 2.3. Extract hooks, custom models, and agent services

This step answers whether the more stateful agent behaviours can become
configurable roles while respecting client-specific capability differences. The
outcome informs the final retirement of the local `agent_tools` role. See
`ansible/roles/agent_tools/tasks/main.yml` §§523-614 and §§849-1063,
`docs/developers-guide.md` §Factory Droid Custom Models, and
`docs/users-guide.md` §Factory Droid DeepSeek Models.

- [ ] 2.3.1. Create an agent hooks role with explicit client capability flags.
  - Requires 2.2.3.
  - Preserve Codex and Claude stop-hook behaviour, preserve Factory Droid hook
    behaviour, and keep Cursor hook installation disabled because Cursor CLI
    does not currently support stop hooks.
  - Success: client capabilities are data-driven, and tests prove Cursor does
    not receive unsupported stop-hook configuration.
- [ ] 2.3.2. Create a Factory Droid custom models role.
  - Requires 2.3.1.
  - Wrap `factory_droid_model` with configurable model entries, provider,
    endpoint, display name, and secret source variable.
  - Success: the DeepSeek models remain present with `provider: anthropic` and
    `baseUrl: https://api.deepseek.com/anthropic`, without exposing the API
    key in logs.
- [ ] 2.3.3. Create an agent user-services role.
  - Requires 2.3.1.
  - Move Droid and Lody systemd user service management behind variables for
    enablement, command, service file, login token availability, and check-mode
    handling.
  - Success: disabled services are stopped when service files exist, enabled
    services start only when required secrets are available, and check mode has
    deterministic results.
- [ ] 2.3.4. Retire the remaining local `agent_tools` responsibilities.
  - Requires 2.3.2 and 2.3.3.
  - Replace the final local task blocks with collection role calls and remove
    migration-only static tests that now have direct role coverage.
  - Success: `agent_tools` is empty, removed, or reduced to a compatibility
    wrapper with no unique behavioural ownership.

## 3. Configurable host and toolchain provisioning

Idea: if the system package and toolchain install roles can be parameterized
without changing the default managed-host profile, the playbook can support
host-specific profiles while keeping the current Rocky Linux environment boring
to operate.

This phase moves the second group of candidates after the agent-tooling split
has established the collection role pattern. Each slice preserves one real
provisioning outcome: host RPM packages, infrastructure CLIs, and user-level
language package managers.

### 3.1. Extract base system packages

This step answers whether the RPM package list can be made configurable while
preserving the current default package set. The outcome informs how host
profiles add or remove packages without editing role internals. See
`ansible/roles/packages/tasks/main.yml` §§2-75 and `docs/developers-guide.md`
§Dependencies.

- [ ] 3.1.1. Create a `packaging.tools` role for Rocky system packages.
  - Requires phase 2.
  - Move CRB enablement, EPEL installation, and default RPM package lists into
    a collection role with override and extension variables.
  - Success: the default profile still installs the existing package list,
    including `ninja-build` and `python3-tomlkit`.
- [ ] 3.1.2. Add package-profile tests.
  - Requires 3.1.1.
  - Cover default packages, extra packages, disabled optional package groups,
    and check-mode behaviour after repository changes.
  - Success: tests prove package configuration changes do not require editing
    the role task file.
- [ ] 3.1.3. Switch `ansible/site.yml` to the collection package role.
  - Requires 3.1.2.
  - Keep the local role name only if needed as a temporary wrapper.
  - Success: `make check` preserves the host-level role ordering from
    `ansible/site.yml` §§7-13.

### 3.2. Extract infrastructure CLI installation

This step answers whether network-dependent infrastructure tools can be tested
through configurable release metadata and installer contracts. The outcome
informs the policy for future tools that require upstream release discovery. See
 `ansible/roles/infra_tools/tasks/main.yml` §§2-88.

- [ ] 3.2.1. Create a `packaging.tools` infrastructure CLI role.
  - Requires 3.1.3.
  - Parameterize OpenTofu repository definitions, TFLint installation, and
    Conftest release lookup.
  - Success: default variables reproduce the current OpenTofu, TFLint, and
    Conftest install behaviour.
- [ ] 3.2.2. Add deterministic tests for release-driven installers.
  - Requires 3.2.1.
  - Stub release metadata and architecture mapping so success and failure paths
    can be tested without live GitHub API calls.
  - Success: tests cover missing release metadata, unsupported architecture,
    and already-installed commands.
- [ ] 3.2.3. Replace the local `infra_tools` role call.
  - Requires 3.2.2.
  - Switch the playbook to the collection role and keep the same host-stage
    ordering.
  - Success: `make check` and role tests agree on the rendered installer
    sequence.

### 3.3. Extract language package-manager tool lists

This step answers whether Rust, Python, and Bun tool lists can become
host-profile data while preserving the default owner environment. The outcome
informs future additions such as optional agent CLIs and pinned tool versions.
See `ansible/roles/rust_crates/tasks/main.yml` §§2-46,
`ansible/roles/uv_tools/tasks/main.yml` §§2-32, and
`ansible/roles/node_packages/tasks/main.yml` §§2-58.

- [ ] 3.3.1. Create configurable collection roles for Rust, `uv`, and Bun
  tools.
  - Requires 3.2.3.
  - Move hard-coded crate, Python tool, and Bun package lists into defaults
    with per-item version, spec, trust, enablement, and path settings.
  - Success: default variables install the same tools as the current local
    roles.
- [ ] 3.3.2. Add role tests for optional and trusted package entries.
  - Requires 3.3.1.
  - Cover Droid and Lody enablement flags, trusted Bun postinstall packages,
    Git-backed `uv` specs, and cargo-binstall path configuration.
  - Success: tests fail if optional entries install when disabled or if trusted
    postinstall settings are lost.
- [ ] 3.3.3. Replace local language tool roles with collection roles.
  - Requires 3.3.2.
  - Preserve role ordering around `rustup`, `paths`, `cursor_cli`, and
    `agent_tools` until those dependencies are explicitly removed.
  - Success: the owner-user stage in `ansible/site.yml` still provisions the
    same user-level toolchain.

## 4. Deferred extensions after the extraction spine

Idea: if the core extraction work is already trustworthy and boring to operate,
broader reuse and distribution can be evaluated on their product value instead
of destabilizing the current managed-host automation.

This phase keeps speculative work out of the core extraction sequence. The
items are useful, but they do not need to block the first role-collection
migration.

### 4.1. Evaluate collection publication and reuse

This step answers whether the extracted collections should remain repository
internal or become published artefacts for other environments. See
`docs/developers-guide.md` §Validation and `ansible/ansible_collections/`.

- [ ] 4.1.1. Decide whether to publish `agentic.agent_configs` and
  `packaging.tools`.
  - Requires phase 3.
  - Define versioning, changelog, dependency, and release-test requirements.
  - Success: the repository has a documented publish-or-internal decision for
    each collection.
- [ ] 4.1.2. Add release packaging checks if publication is approved.
  - Requires 4.1.1.
  - Validate `galaxy.yml`, collection docs, and install-from-tarball behaviour.
  - Success: collection artefacts can be built and tested without the site
    playbook.

### 4.2. Evaluate richer role execution environments

This step answers whether local role tests are enough or whether containerized
role scenarios are worth the added operational cost. See `Makefile` §§68-70 and
`docs/developers-guide.md` §Validation.

- [ ] 4.2.1. Compare the current role-test harness with Molecule-style
  scenarios.
  - Requires phase 3.
  - Evaluate filesystem isolation, systemd user service coverage, DNF
    availability, and secret handling.
  - Success: one documented decision explains whether containerized role tests
    are adopted, deferred, or rejected.
- [ ] 4.2.2. Add containerized scenarios only for gaps the local harness cannot
  cover.
  - Requires 4.2.1.
  - Start with package and service roles if local tests cannot exercise their
    real side effects.
  - Success: any added scenario covers a named gap and does not duplicate
    cheaper local tests.
