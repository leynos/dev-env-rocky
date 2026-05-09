# Record the collection boundary

This ExecPlan (execution plan) is a living document. The sections
`Constraints`, `Tolerances`, `Risks`, `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work
proceeds.

Status: DRAFT

## Purpose / big picture

Roadmap item 1.1.1 needs one accepted architectural decision record (ADR) that
draws the boundary between reusable Ansible collection behaviour and
site-local orchestration. An ADR is a short design document that records a
decision, the context that led to it, and the consequences of following it.

After this change is implemented, a maintainer can read the new ADR and know
which extraction candidates belong to `agentic.agent_configs`,
`packaging.tools`, or the private site playbook. The visible result is that
`docs/roadmap.md` item 1.1.1 is checked off and links to the accepted decision.
No role tasks should move during this work; the point is to create the contract
that later role extraction work must follow.

## Constraints

- Do not implement the plan until the user explicitly approves it. Drafting
  this file is the only approved change in the current phase.
- Scope implementation to documentation and documentation validation unless a
  test or lint gate proves a small supporting test update is required.
- Do not move Ansible tasks between roles and collections in this milestone.
- Do not change `ansible/site.yml` behaviour or managed-host provisioning
  output in this milestone.
- Preserve the existing user-visible behaviour documented in
  `docs/users-guide.md`: `make site`, `make check`, agent configuration paths,
  Firecrawl Model Context Protocol (MCP) registration, package installation,
  and service behaviour must remain descriptive of the current playbook.
- Follow `docs/documentation-style-guide.md`: British English with Oxford
  spelling, concise operator-focused prose, expanded uncommon acronyms, and no
  plaintext secrets.
- Follow the local `AGENTS.md` Markdown rules: wrap prose and bullets at 80
  columns, use dashes for list bullets, run Markdown validation for docs
  changes, and run all gates through `tee` logs.
- Treat `docs/falcon-correlation-id-middleware-design.md` as unavailable in
  this checkout unless it appears before implementation starts. It was named in
  the request but is not present under `docs/`.
- Use `docs/complexity-antipatterns-and-refactoring-strategies.md` as a
  refactoring and complexity signpost when the ADR discusses why role
  extraction should avoid broad, tangled relocation work.
- Use `grepai` first for semantic code exploration when it is available. If
  the local Qdrant endpoint is still unavailable, record the fallback to exact
  repository reads in `Surprises & Discoveries`.
- Use `leta` for symbol-level code exploration if implementation unexpectedly
  touches Python or Ansible module code. This plan is documentation-first, so
  symbol-level exploration is not expected.
- Commit only after the applicable gates for the change have passed.

## Tolerances (exception triggers)

- Scope: if implementation requires changing more than six files, stop and
  ask for approval before continuing.
- Behaviour: if implementation would require changing any task under
  `ansible/roles/` or any module under `ansible/ansible_collections/`, stop and
  ask for approval.
- Interfaces: if the ADR cannot classify all requested candidates without
  inventing new variables, public role defaults, or collection APIs, stop and
  present the unresolved choices.
- Dependencies: if validating the docs requires adding a new dependency such
  as `pytest-bdd`, `hypothesis`, or a Markdown plugin, stop and ask for
  approval. Do not add dependencies just to satisfy a documentation-only
  milestone.
- Validation: if `make check-fmt`, `make typecheck`, `make lint`, or
  `make test` fails after two fix attempts for reasons caused by this branch,
  stop and record the failures.
- Documentation gates: if `make markdownlint` or `make nixie` fails for
  unrelated pre-existing files, record the exact failing files and continue
  only with user approval or a narrowly scoped fix.
- Ambiguity: if two ownership classifications both appear valid and materially
  change later roadmap sequencing, stop and ask the user to choose.

## Risks

- Risk: The current repository already contains an extraction direction in
  `docs/adr-001-public-private-split.md`, and the new ADR could contradict it.
  Severity: medium. Likelihood: medium. Mitigation: write the new ADR as a
  refinement of ADR-001's public/private split rather than a replacement, and
  cross-link the two documents.

- Risk: `agent_tools` contains reusable patterns and site-specific secrets,
  repositories, and service wiring in the same role. Severity: high.
  Likelihood: high. Mitigation: classify the current role as site-local while
  naming the reusable slices that later roadmap phases may extract into
  `agentic.agent_configs`.

- Risk: Package installation responsibilities are split between current site
  roles and existing `packaging.tools` modules. Severity: medium. Likelihood:
  high. Mitigation: distinguish reusable package-manager primitives from the
  site's selected package lists, repositories, symlinks, and feature flags.

- Risk: This is a documentation-only roadmap task, but the request includes
  unit, behavioural, Molecule, end-to-end, and property-test guidance.
  Severity: medium. Likelihood: medium. Mitigation: add lightweight `pytest`
  documentation checks if they materially protect the ADR contract, explain why
  `pytest-bdd`, Molecule, end-to-end tests, and Hypothesis are not applicable
  unless behaviour changes, and still run the required Python and Markdown
  gates.

- Risk: The prompt names `docs/falcon-correlation-id-middleware-design.md`,
  which is absent from the current checkout. Severity: low. Likelihood: high.
  Mitigation: record its absence and do not cite it as a source of current
  repository truth unless it appears before implementation starts.

## Relevant documentation and skills

Use these documents as source material while implementing this plan:

- `docs/roadmap.md`, especially roadmap item 1.1.1 under
  "Foundational extraction contracts".
- `docs/adr-001-public-private-split.md`, especially the "Collection
  extraction" section.
- `docs/documentation-style-guide.md` for prose style and secret-handling
  rules.
- `docs/complexity-antipatterns-and-refactoring-strategies.md`, especially its
  guidance on cyclomatic complexity, cognitive complexity, and the Bumpy Road
  antipattern. Use it to justify staged extraction over broad role relocation.
- `docs/developers-guide.md`, especially "Structured File Modules",
  "Firecrawl MCP", "Tool Package Modules", "Dependencies", and "Validation".
- `docs/users-guide.md`, especially "Agent Configuration", "System Packages",
  "Factory Droid DeepSeek Models", and "Firecrawl MCP".
- `ansible/site.yml`, because its current role order shows which
  responsibilities run in the server play and which run in the owner-user play.
- `ansible/roles/agent_tools/tasks/main.yml`,
  `ansible/roles/packages/tasks/main.yml`,
  `ansible/roles/infra_tools/tasks/main.yml`,
  `ansible/roles/rust_crates/tasks/main.yml`,
  `ansible/roles/uv_tools/tasks/main.yml`, and
  `ansible/roles/node_packages/tasks/main.yml`.
- `ansible/ansible_collections/agentic/agent_configs/README.md` and
  `ansible/ansible_collections/agentic/agent_configs/galaxy.yml`.
- `ansible/ansible_collections/packaging/tools/galaxy.yml` and its module
  tests under
  `ansible/ansible_collections/packaging/tools/tests/unit/plugins/modules/`.

Use these skills and tools:

- `execplans`, for keeping this document self-contained and current.
- `leta`, if symbol-level code understanding becomes necessary.
- `grepai`, as the primary semantic exploration tool when its local index is
  available; exact file reads are the fallback.
- The Wyvern agent team, only for bounded read-only reconnaissance. Sub-agents
  must not edit files or run tests.

## Current orientation

The existing playbook has two broad execution surfaces. The first play in
`ansible/site.yml` runs as root against `servers` and includes `system`,
`packages`, `infra_tools`, `user`, and `user_linger`. The third play runs as
the owner user on hosts where that user exists and includes `git`, `rustup`,
`rust_crates`, `uv_tools`, `node_packages`, `go_packages`, `paths`,
`cursor_cli`, `agent_tools`, `sccache_user`, optionally `rust_cleanup`, and
`weave`.

The repository already contains two Ansible collection directories:
`agentic.agent_configs` and `packaging.tools`. `agentic.agent_configs` owns
configuration modules for Codex, Claude Code, Cursor CLI, Factory Droid, JSON,
and TOML files. `packaging.tools` owns package-manager modules for Bun, uv, and
`cargo-binstall`. Some package modules still also exist under
`agentic.agent_configs`, so the ADR must identify this as a cleanup consequence
rather than silently blessing duplicate ownership.

The current candidate classification to validate during implementation is:

- Extract now: the `agentic.agent_configs` module collection and the
  `packaging.tools` package-manager module collection.
- Extract later: reusable role patterns in `packages`, `infra_tools`,
  `rust_crates`, `uv_tools`, and `node_packages`, after role variable
  contracts and direct role validation are established.
- Site-local now: the current `agent_tools` role as a whole, because it mixes
  private repositories, SSH key lifecycle, vaulted secrets, owner-specific MCP
  registration, hooks, custom models, and user services. Later roadmap phases
  may extract specific reusable slices from it.

## Implementation plan

Start by rereading this ExecPlan, `docs/roadmap.md`, and
`docs/adr-001-public-private-split.md`. Confirm that the branch is still
`1-1-1-architectural-decision-record-for-collection-boundary` with
`git branch --show`. If the branch changed, stop and ask whether the plan path
or roadmap item should change.

Create `docs/adr-002-collection-boundary.md` following the existing ADR style:
title, `Status: Accepted`, date, `Context`, `Decision`, and `Consequences`.
The ADR must define the boundary between the two reusable collections and
site-local orchestration in plain language. It must identify collection-owned
behaviour, site-owned orchestration, and the rule for future extraction slices:
only behaviour with configurable inputs, no private inventory assumptions, and
direct validation belongs in a collection role.

In the ADR decision, classify every requested candidate:

- `agent_tools`: site-local now; extract specific agent configuration slices
  later into `agentic.agent_configs` roles once variable contracts and role
  tests exist.
- `packages`: extract later into `packaging.tools` as a Rocky/system package
  role after the package list is configurable and host-profile tests exist.
- `infra_tools`: extract later, probably under `packaging.tools` or a later
  infrastructure collection, after installer and repository inputs are
  configurable and pinned.
- `rust_crates`: extract later into `packaging.tools` once bootstrap of
  `cargo-binstall`, crate lists, roots, and version pins have a documented
  variable contract.
- `uv_tools`: extract later into `packaging.tools` once the selected tool list
  and Git-backed specs are data rather than fixed role internals.
- `node_packages`: extract later into `packaging.tools`; it already has
  Molecule coverage, but site-specific symlinks and enablement flags need a
  stable variable contract before role extraction.

Update `docs/developers-guide.md` with a short collection-boundary section.
It should point to the new ADR and summarise how contributors decide whether a
future change belongs in `agentic.agent_configs`, `packaging.tools`, or a
site-local role. Keep this as internal-facing guidance; do not duplicate the
whole ADR.

Update `docs/users-guide.md` only for user-visible clarity. Add a short note
near "Agent Configuration" or the relevant package sections explaining that the
current playbook still provisions the same outputs, while the ADR defines the
future extraction boundary. Do not promise a new command or behaviour that does
not exist.

Update `docs/adr-001-public-private-split.md` only if needed to point its
"Collection extraction" section at the new ADR. Avoid rewriting its historical
decision.

Update `docs/roadmap.md` item 1.1.1. Add a link to the new ADR and check the
item off only after the ADR and supporting guide links have landed and gates
pass. Do not check off later items 1.1.2 or 1.1.3.

Consider adding a focused `pytest` documentation test if it protects the
contract cheaply. A suitable test would assert that the ADR contains all six
candidate names and the three ownership classes. Do not add a test if it would
force brittle prose matching or require new dependencies. `pytest-bdd`,
Molecule, end-to-end tests, and Hypothesis are not expected for this
documentation-only task because no executable behaviour, playbook path,
network boundary, persistence contract, or input invariant changes.

Run formatting and validation through `tee` logs under `/tmp`, using the branch
name in each log path. At minimum run:

```bash
make check-fmt 2>&1 | tee /tmp/check-fmt-dev-env-rocky-1-1-1-architectural-decision-record-for-collection-boundary.out
make typecheck 2>&1 | tee /tmp/typecheck-dev-env-rocky-1-1-1-architectural-decision-record-for-collection-boundary.out
make lint 2>&1 | tee /tmp/lint-dev-env-rocky-1-1-1-architectural-decision-record-for-collection-boundary.out
make test 2>&1 | tee /tmp/test-dev-env-rocky-1-1-1-architectural-decision-record-for-collection-boundary.out
make markdownlint 2>&1 | tee /tmp/markdownlint-dev-env-rocky-1-1-1-architectural-decision-record-for-collection-boundary.out
make nixie 2>&1 | tee /tmp/nixie-dev-env-rocky-1-1-1-architectural-decision-record-for-collection-boundary.out
git diff --check 2>&1 | tee /tmp/diff-check-dev-env-rocky-1-1-1-architectural-decision-record-for-collection-boundary.out
```

If any gate fails because of the new documentation, fix the documentation and
rerun the failing gate. If a gate fails because of unrelated pre-existing
state, record the exact failure and ask for direction before committing unless
the fix is obviously docs-scoped and within this plan's tolerances.

After all applicable gates pass, commit the completed roadmap item and
supporting documentation in one focused commit. The commit message should be in
imperative mood, for example:

```plaintext
Record collection boundary ADR

Add the accepted ADR for roadmap item 1.1.1 and link the
developer, user, and roadmap documentation to the new ownership
boundary.
```

## Validation plan

The implementation is successful when all of these are true:

- `docs/adr-002-collection-boundary.md` exists, has `Status: Accepted`, and
  identifies `agentic.agent_configs`, `packaging.tools`, and site-local
  orchestration ownership.
- The ADR classifies `agent_tools`, `packages`, `infra_tools`,
  `rust_crates`, `uv_tools`, and `node_packages` as extract-now,
  extract-later, or site-local, with rationale.
- `docs/developers-guide.md` links to the ADR and gives contributors a concise
  rule for future collection versus site-local changes.
- `docs/users-guide.md` remains accurate for current playbook behaviour and
  mentions the boundary only where it helps users understand ownership.
- `docs/roadmap.md` item 1.1.1 is checked off and links to the ADR; no later
  roadmap task is marked complete.
- If a focused documentation test is added, it fails before the ADR exists or
  omits the required classifications and passes after the ADR is complete.
- `make check-fmt`, `make typecheck`, `make lint`, and `make test` pass.
- `make markdownlint`, `make nixie`, and `git diff --check` pass or have an
  explicitly recorded, unrelated blocker.

Molecule with Podman is not required unless implementation changes role or
playbook behaviour. If a role or playbook change becomes necessary, stop before
making it because that exceeds this plan's intended scope.

## Progress

- [x] 2026-05-09 14:07 BST: Confirmed the active branch is
  `1-1-1-architectural-decision-record-for-collection-boundary`.
- [x] 2026-05-09 14:07 BST: Loaded the `leta` and `execplans` skills and read
  the repository `AGENTS.md`.
- [x] 2026-05-09 14:07 BST: Requested read-only Wyvern reconnaissance for
  documentation conventions and Ansible boundary classification.
- [x] 2026-05-09 14:07 BST: Read `docs/roadmap.md`,
  `docs/developers-guide.md`, `docs/users-guide.md`,
  `docs/documentation-style-guide.md`, `docs/adr-001-public-private-split.md`,
  `ansible/site.yml`, candidate role task files, collection metadata, and
  `Makefile`.
- [x] 2026-05-09 14:07 BST: Drafted this ExecPlan and left implementation
  blocked pending explicit approval.
- [x] 2026-05-09 14:18 BST: Confirmed the user added
  `docs/complexity-antipatterns-and-refactoring-strategies.md`, updated this
  plan to signpost it, and confirmed
  `docs/falcon-correlation-id-middleware-design.md` remains absent.

## Surprises & Discoveries

- `grepai` was unavailable during planning because its Qdrant endpoint at
  `127.0.0.1:6334` refused connections. Exact repository reads were used as
  the fallback.
- `leta files | head` printed the expected repository overview but then
  aborted on a broken pipe after `head` closed stdout. The repository was still
  added to the `leta` workspace before that happened.
- The requested signpost file
  `docs/falcon-correlation-id-middleware-design.md` remains absent from this
  checkout.
- The requested signpost file
  `docs/complexity-antipatterns-and-refactoring-strategies.md` is now present
  and should inform the ADR's rationale for staged extraction.
- There is no top-level `pyproject.toml`; Python gates route through the
  `python/rust_cleanup` project and repository test directory as defined in
  `Makefile`.
- No current test file or project metadata references `pytest-bdd`, so adding
  behavioural tests for a documentation-only ADR would require new dependency
  discussion.
- `packaging.tools` has `galaxy.yml` and module tests but no top-level
  `README.md` or example playbook in the current tree, unlike
  `agentic.agent_configs`.

## Decision Log

- Decision: Treat roadmap item 1.1.1 as a documentation contract milestone,
  not a role extraction milestone. Rationale: the roadmap success criterion is
  "one accepted decision", and later items own compatibility rules, variable
  contracts, and role-level validation scaffolding.

- Decision: Draft the future implementation around `ADR-002` rather than
  editing ADR-001 in place. Rationale: ADR-001 records the public/private split;
  1.1.1 needs a more specific collection-boundary decision that builds on it.

- Decision: Use Wyvern agents for read-only reconnaissance only. Rationale:
  the user requested a Wyvern agent team, while local instructions prohibit
  sub-agents from running tests and the current phase is planning.

- Decision: Keep `agent_tools` site-local in the initial classification while
  allowing later extraction of specific slices. Rationale: the current role
  contains private repository setup, SSH key lifecycle, vaulted secret use,
  MCP registration, custom models, hooks, and user services; moving it as a
  whole would blur the boundary the ADR is meant to clarify.

- Decision: Do not require Molecule, end-to-end, property, or `pytest-bdd`
  tests for the ADR itself. Rationale: this milestone should not change
  executable playbook behaviour. The plan still requires the normal Python and
  Markdown gates and allows focused `pytest` documentation checks if useful.

## Outcomes & Retrospective

This section is intentionally empty while the plan is in draft. During
implementation, record the final files changed, validation log paths, commit
hash, and any lessons that should affect later roadmap items 1.1.2 and 1.1.3.
