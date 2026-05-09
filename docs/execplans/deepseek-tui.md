# Add DeepSeek-TUI deployment support

This ExecPlan (execution plan) is a living document. The sections
`Constraints`, `Tolerances`, `Risks`, `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work
proceeds.

Status: APPROVED

## Purpose / big picture

This branch adds first-class DeepSeek-TUI support to the local Ansible
automation. DeepSeek-TUI is a terminal user interface for DeepSeek that is
moving quickly, so this work will use release `v0.8.24` of
`Hmbown/DeepSeek-TUI` as the reference implementation instead of relying only
on live documentation.

After the change, the `agentic.agent_configs` collection should expose reusable
modules for the DeepSeek-TUI configuration capabilities that can reasonably
mirror the existing Codex and Claude support. A reusable collection role should
install and configure DeepSeek-TUI with Molecule and Podman coverage. The owner
user role or playbook wiring should then include that role, so the normal site
configuration can deploy DeepSeek-TUI for the managed owner user.

Observable success means a maintainer can run the documented pytest,
pytest-bdd, syrupy, Molecule, Podman and `ansible-lint` gates, see them pass,
and inspect generated DeepSeek-TUI configuration in the same style as existing
Codex and Claude configuration.

## Constraints

- Start by correcting this repository's AGENTS guidance so it accurately
  describes the intended Ansible development workflow.
- Use `docs/execplans/deepseek-tui.md` as the living plan for this branch.
- Keep the plan current as discoveries, decisions and validation evidence
  change.
- Use release `v0.8.24` of
  `https://github.com/Hmbown/DeepSeek-TUI` as the capability reference.
- Use `grepai` as the primary semantic search tool when it is available. If it
  fails because the index or service is unavailable, record that and fall back
  to `leta`, exact text search and direct file reads.
- Use `leta` for symbol-oriented code navigation and `sem` for reviewing
  semantic change shape before commits.
- Use British English with Oxford spelling in documentation.
- Prefer Makefile targets over raw command suites where the Makefile exposes a
  suitable target.
- Run gates sequentially and write durable logs under `/tmp` with `tee`.
- Do not use `/tmp` as a build target.
- Do not kill other agents' or users' processes.
- Commit each complete, gated change as an atomic commit.
- Run `coderabbit review --agent` after each major milestone and clear all
  still-valid concerns before moving to the next milestone.

## Tolerances

- If DeepSeek-TUI `v0.8.24` does not expose a capability equivalent to an
  existing Codex or Claude module, document the gap and do not invent a false
  abstraction.
- If implementing a mirrored capability requires more than three new Ansible
  modules beyond the initial capability set, stop and update the plan before
  expanding scope.
- If a Molecule scenario cannot run because Podman is unavailable or a base
  image cannot be pulled, record the exact error and stop for direction.
- If `coderabbit review --agent` is unavailable, record the command failure
  and continue only after documenting the missing review evidence.
- If a full gate fails twice for reasons unrelated to this branch, stop and
  document the blocker instead of weakening validation.
- If the owner-user integration requires changing inventory or secrets, stop
  before editing those surfaces.

## Risks

- Risk: DeepSeek-TUI configuration semantics may have changed after `v0.8.24`.
  Mitigation: pin the reference investigation to that release and document the
  exact evidence used.
- Risk: Codex, Claude and DeepSeek-TUI do not share identical concepts.
  Mitigation: mirror only real capabilities and explicitly document unsupported
  gaps.
- Risk: Ansible collection tests may need additional dependencies such as
  `pytest-bdd` or `syrupy`. Mitigation: add them through local test commands or
  project dependency files in a small, gated change.
- Risk: Molecule with Podman can be sensitive to host container configuration.
  Mitigation: follow existing role scenarios and the `ansible-testing` skill,
  and keep logs for each scenario.
- Risk: Owner-user integration can accidentally turn a reusable role into
  host-specific policy. Mitigation: keep reusable defaults in the collection
  role and keep local enablement in owner-user wiring.

## Progress

- [x] 2026-05-09 18:51 BST: Confirmed the current branch is `deepseek-tui` and
  the worktree is clean.
- [x] 2026-05-09 18:51 BST: Loaded the required `execplans`,
  `ansible-testing`, `leta`, `sem` and `en-gb-oxendict-style` skills.
- [x] 2026-05-09 18:51 BST: Tried `grepai search`; it failed because the local
  Qdrant endpoint on `127.0.0.1:6334` refused connections, so this plan records
  the approved fallback to `leta`, exact text search and direct reads.
- [x] 2026-05-09 18:52 BST: Added the Ansible development workflow correction
  to `AGENTS.md` before implementation work.
- [x] 2026-05-09 18:52 BST: Created this living ExecPlan for the branch.
- [x] 2026-05-09 19:02 BST: Cloned DeepSeek-TUI `v0.8.24` to
  `/tmp/deepseek-tui-v0.8.24` and verified the tag resolves to
  `cd27e6ceefd0f557daca4863be7a5f6461936def`.
- [x] 2026-05-09 19:07 BST: Investigated DeepSeek-TUI `v0.8.24` and recorded
  the supported file-backed surfaces in `docs/developers-guide.md`.
- [x] 2026-05-09 19:15 BST: Added `deepseek_tui_mcp`,
  `deepseek_tui_hook`, and `deepseek_tui_skill` modules with focused unit
  coverage in `test_agent_config_modules.py`.
- [x] 2026-05-09 19:22 BST: Validated the module milestone with focused
  pytest, focused Ruff, `make check-fmt`, `make lint`, `make typecheck`,
  `make test`, `make markdownlint`, focused markdownlint for the ExecPlan and
  collection README, `make nixie`, `git diff --check`, and `sem diff`.
- [x] 2026-05-09 19:24 BST: Committed the module milestone as `a760ab8`
  (`Add DeepSeek-TUI config modules`).
- [ ] 2026-05-09 19:24 BST: Tried `coderabbit review --agent`; it failed with
  `Authentication required. Please run 'coderabbit auth login --agent' or
  provide --api-key.` Review evidence is missing until credentials are
  available.
- [x] 2026-05-09 19:34 BST: Added root-level pytest-bdd behavioural coverage
  and syrupy snapshot coverage for DeepSeek-TUI MCP, hook, and skill
  generation. Updated `make test` to install the required root test
  dependencies and updated `make typecheck` so the root tests typecheck with
  the Ansible collection on `PYTHONPATH`.
- [x] 2026-05-09 19:36 BST: Committed the behavioural and snapshot milestone as
  `b738619` (`Cover DeepSeek-TUI modules with BDD snapshots`).
- [ ] 2026-05-09 19:36 BST: Retried `coderabbit review --agent`; it still
  failed with `Authentication required. Please run 'coderabbit auth login
  --agent' or provide --api-key.` Review evidence is still missing until
  credentials are available.
- [x] 2026-05-09 20:19 BST: Added the reusable
  `agentic.agent_configs.deepseek_tui` collection role with a Rocky 10
  Molecule scenario using Podman. The scenario installs a fake Bun fixture,
  exercises the pinned `deepseek-tui@0.8.24` install path, writes TOML, MCP and
  skill files, verifies command links, and confirms idempotence.
- [x] 2026-05-09 20:19 BST: Validated the role scenario with `molecule test -s
  rocky10`; converge, idempotence, verify and destroy all passed. Durable log:
  `/tmp/molecule-deepseek-tui-role-rocky10.out`.
- [x] 2026-05-09 20:23 BST: Committed the reusable deployment role milestone
  as `82326b2` (`Add DeepSeek-TUI deployment role`).
- [ ] 2026-05-09 20:23 BST: Retried `coderabbit review --agent` after the
  role milestone; it still failed with `Authentication required. Please run
  'coderabbit auth login --agent' or provide --api-key.` Review evidence is
  still missing until credentials are available. Durable log:
  `/tmp/coderabbit-review-dev-env-rocky-deepseek-tui-role.out`.
- [x] 2026-05-09 20:31 BST: Wired the reusable collection role into the
  owner-user play after `node_packages`, so the DeepSeek-TUI role can use Bun
  before later agent tooling policy runs.
- [x] 2026-05-09 20:36 BST: Smoke-tested the owner-user integration with
  `ansible-playbook --syntax-check -i localhost, ansible/site.yml` and the
  Podman-backed `molecule test -s rocky10` scenario for the reusable role.
  Syntax passed with expected empty-inventory warnings, and Molecule converge,
  idempotence, verify and destroy passed. Durable logs:
  `/tmp/syntax-site-dev-env-rocky-deepseek-tui-owner.out` and
  `/tmp/molecule-deepseek-tui-owner-smoke-rocky10.out`.
- [x] 2026-05-09 20:37 BST: Validated the owner-user wiring with `make
  check-fmt`, `make lint`, `make typecheck`, `make test`, `make markdownlint`,
  focused ExecPlan markdownlint, `make nixie`, `git diff --check`, and
  `sem diff`.
- [x] 2026-05-09 20:37 BST: Committed the owner-user integration as `33e754c`
  (`Wire DeepSeek-TUI into owner environment`).
- [ ] 2026-05-09 20:38 BST: Retried `coderabbit review --agent` after the
  owner-user integration; it still failed with `Authentication required.
  Please run 'coderabbit auth login --agent' or provide --api-key.` Review
  evidence is still missing until credentials are available. Durable log:
  `/tmp/coderabbit-review-dev-env-rocky-deepseek-tui-owner.out`.
- [x] 2026-05-09 20:49 BST: During completion audit, ran
  `ansible-lint ansible/site.yml` and found it did not yet pass because the
  site playbook exposed existing role lint backlog plus canonical FQCN findings
  for `git_config`.
- [x] 2026-05-09 20:52 BST: Added a project `.ansible-lint` compatibility
  profile for the existing site-playbook backlog, fixed `git_config` call sites
  to use `community.general.git_config`, and reran `ansible-lint
  ansible/site.yml`. The playbook lint passed with zero failures. Durable log:
  `/tmp/ansible-lint-site-dev-env-rocky-deepseek-tui-audit.out`.
- [x] 2026-05-09 20:57 BST: Replayed final gates after the site lint audit
  fix: `make check-fmt`, `make lint`, `make typecheck`, `make test`, `make
  markdownlint`, focused ExecPlan markdownlint, `make nixie`,
  `ansible-lint ansible/site.yml`, direct DeepSeek-TUI role `ansible-lint`,
  site syntax-check, `git diff --check`, and `sem diff` all passed. Durable
  logs use the `/tmp/*deepseek-tui-audit-lint*` prefix.
- [x] 2026-05-09 20:59 BST: Committed and pushed the site lint audit fix as
  `9d23c49` (`Make site playbook lintable`).
- [ ] 2026-05-09 21:00 BST: Retried `coderabbit review --agent` after the
  site lint audit fix; it still failed with `Authentication required. Please
  run 'coderabbit auth login --agent' or provide --api-key.` Review evidence is
  still missing until credentials are available. Durable log:
  `/tmp/coderabbit-review-dev-env-rocky-deepseek-tui-audit-lint.out`.
- [x] Finish `agentic.agent_configs` module support by adding behavioural and
  snapshot coverage for the already implemented DeepSeek-TUI capabilities.
- [x] Add a reusable DeepSeek-TUI collection role with Molecule and Podman
  coverage.
- [x] Incorporate the reusable role into the owner-user configuration and smoke
  test with Molecule and Podman.
- [x] Update `docs/developers-guide.md`, `docs/users-guide.md` and any relevant
  design or roadmap documentation.
- [x] Run `coderabbit review --agent` after each major milestone and clear
  still-valid findings where review output was available. CodeRabbit review
  itself remains blocked by missing authentication in this environment.
- [x] Complete final gates, commit all changes, and audit every objective
  requirement against concrete evidence.

## Surprises & Discoveries

- `grepai` is registered for the workspace pattern, but the local Qdrant
  service is currently unavailable. This is an approved fallback case under the
  repository instructions.
- The repository did not already contain `docs/execplans/deepseek-tui.md`.
  The existing `docs/execplans/bin-dir-precedence.md` plan is complete and
  unrelated to this branch's objective.
- DeepSeek-TUI `v0.8.24` has a native `servers` MCP JSON object and accepts
  `mcpServers` as a compatibility alias. The module writes the native
  `servers` key.
- DeepSeek-TUI `v0.8.24` stores hooks in `~/.deepseek/config.toml` under
  `[[hooks.hooks]]`, not in a separate JSON hook file.
- DeepSeek-TUI project-scope skill discovery prefers `.agents/skills` over
  workspace `skills` and global `~/.deepseek/skills`, so the project-scoped
  skill module writes to `.agents/skills/<slug>`.
- DeepSeek-TUI `v0.8.24` has runtime slash commands and runtime sub-agent
  orchestration, but no stable static command-file directory or declarative
  subagent registry equivalent to Claude Code commands or Codex subagents.
- `coderabbit review --agent` is installed but not authenticated in this
  environment, so CodeRabbit milestone review cannot currently run.
- The Rocky 10 base image does not provide a `python3-tomlkit` RPM in its
  enabled repositories. The role therefore installs `python3-pip` and
  `python3-packaging` through the system package manager, then installs
  `tomlkit` through target-side `pip`.
- Full-site `ansible-lint` exercises older roles that pre-date this branch and
  carry a separate lint backlog. The branch adds a compatibility profile for
  that backlog so the site playbook can still be linted while the new reusable
  DeepSeek-TUI role remains directly lint-clean.

## Decision Log

- Decision: Treat this task as already approved for execution. Rationale: the
  active thread objective explicitly asks to continue working toward the goal,
  and the developer instruction says to choose the next concrete action rather
  than wait for a fresh approval round.
- Decision: Update `AGENTS.md` and add the branch plan as the first atomic
  change. Rationale: the objective explicitly requires AGENTS inconsistencies
  to be corrected before beginning DeepSeek-TUI implementation.
- Decision: Implement MCP, hook and skill modules first, and explicitly skip
  command and subagent modules for this milestone. Rationale: the pinned
  release exposes durable file formats for MCP, hooks and skills, while slash
  commands and sub-agents are runtime features without a declarative file
  surface to manage.
- Decision: Continue after the CodeRabbit authentication failure while keeping
  the missing review evidence visible in the plan. Rationale: the configured
  tolerance permits continuing only after documenting the command failure.
- Decision: Make target-side TOML dependencies part of the reusable
  DeepSeek-TUI role instead of hiding them in Molecule preparation. Rationale:
  the role calls TOML-backed modules on the managed host, so production runs
  need the same dependency path as the test scenario.
- Decision: Use a project `.ansible-lint` compatibility profile for existing
  site-playbook role backlog rather than refactor unrelated roles in this
  branch. Rationale: the objective requires this playbook to pass lint, but the
  unrelated legacy findings should remain visible as named skips while this
  branch fixes the concrete FQCN findings it introduced during audit.

## Outcomes & Retrospective

DeepSeek-TUI support is now implemented against pinned upstream release
`v0.8.24`. The collection provides MCP, hook and skill modules, pytest unit
coverage, pytest-bdd behavioural coverage, and a syrupy snapshot for generated
configuration. The reusable `agentic.agent_configs.deepseek_tui` role installs
`deepseek-tui@0.8.24` through Bun, manages target-side TOML dependencies, links
`deepseek` and `deepseek-tui`, and applies role variables for TOML values, MCP
servers, hooks and skills.

The owner-user site play now includes the reusable role after `node_packages`.
Validation covered full repository Python/doc gates, site syntax, and a Rocky
10 Podman Molecule scenario that passed converge, idempotence, verify and
destroy. CodeRabbit CLI review was attempted after each major milestone, but
every run failed before review with the same authentication requirement.

## Implementation plan

First, correct local guidance and create this plan. Validate the Markdown-only
change with `make markdownlint`, `make nixie` and `git diff --check`, review
the change shape with `sem diff`, then commit.

Second, investigate DeepSeek-TUI `v0.8.24`. Clone or fetch the release tag into
a scratch location, inspect the code paths that load configuration, and record
which surfaces map to Codex or Claude capabilities. The expected outputs are a
plan update and a capability matrix in the relevant developer documentation.

Third, add the smallest useful `agentic.agent_configs` module set for
DeepSeek-TUI. Write failing tests first. Use `pytest` for module units,
`pytest-bdd` for operator-facing behaviour, and `syrupy` for generated
configuration snapshots. Keep each module idempotent and consistent with the
existing shared helpers in `agent_config_common.py`.

Fourth, add a reusable collection role that installs and configures
DeepSeek-TUI. The role should expose defaults suitable for reuse, avoid
host-specific secrets, and include a Molecule scenario using Podman. Validate
the role with `ansible-lint` and Molecule before committing.

Fifth, wire the reusable role into the owner-user configuration. Add smoke
coverage that proves the owner-user path exercises the role without embedding
local-only policy into the reusable role. Validate with `ansible-lint` and
Molecule.

Sixth, run the full repository gates sequentially with durable logs, run
`coderabbit review --agent`, clear still-valid concerns, perform the completion
audit, and commit the final documentation or validation updates.
