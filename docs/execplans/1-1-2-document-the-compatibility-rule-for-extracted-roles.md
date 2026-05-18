# Document the extracted-role compatibility rule

This ExecPlan (execution plan) is a living document. The sections
`Constraints`, `Tolerances`, `Risks`, `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work
proceeds.

Status: DRAFT

## Purpose / big picture

Roadmap item 1.1.2 needs a written compatibility rule for switching a local
Ansible role to an extracted collection role. An extracted role is a role that
moves reusable behaviour from `ansible/roles/` into an Ansible collection under
`ansible/ansible_collections/`, while the site playbook keeps owner-specific
orchestration.

After this plan is approved and implemented, a maintainer can read the
developers' guide, the boundary architectural decision record (ADR), and the
roadmap entry to know when a playbook call may change from a local role to a
collection role. The visible outcome is a contract that says the switch is
allowed only when the current `make site` and `make check` behaviour remains
the same, or when a later accepted decision deliberately changes the managed
host profile. No role tasks should move during this roadmap item.

## Constraints

- Do not implement this plan until the user explicitly approves it. Drafting,
  validating, committing, pushing, and opening a draft pull request for this
  ExecPlan are the only approved changes in the current phase.
- Scope implementation to documentation and narrowly targeted documentation
  tests. Do not move tasks between local roles and collection roles in item
  1.1.2.
- Preserve the current `make site` and `make check` behaviour documented in
  `docs/users-guide.md` and implemented in `Makefile`. `make check` must remain
  the dry-run plus diff form of the same playbook invocation.
- Do not change `ansible/site.yml` role ordering during this roadmap item.
  Later extraction tasks may switch a call only after this rule and the later
  role-level validation scaffolding are in place.
- Do not introduce new public role variables, collection APIs, Ansible modules,
  Python package dependencies, Molecule scenarios, or pytest-bdd scenarios
  unless the user approves a scope change.
- Follow `docs/documentation-style-guide.md`: British English with Oxford
  spelling, concise operator-focused prose, expanded uncommon acronyms, and no
  plaintext secrets.
- Follow the repository Markdown rules from `AGENTS.md`: wrap prose and
  bullets at 80 columns, use dashes for list bullets, run `make fmt` after
  documentation edits, and run gates with `tee` logs under `/tmp`.
- Treat `docs/falcon-correlation-id-middleware-design.md` as unavailable in
  this checkout unless it appears before implementation starts. It was named in
  the request, but `docs/` does not currently contain that file.
- Use `docs/complexity-antipatterns-and-refactoring-strategies.md` as the
  complexity signpost for why this rule prevents broad, tangled role relocation
  work.
- Use the `leta` skill for code navigation if implementation unexpectedly
  needs symbol-level code understanding. This task is documentation-first, so
  exact Markdown and YAML file reads are expected to be sufficient.
- The requested "ansible testing" skill is not installed in this session. Use
  the repository's Ansible, Molecule, Podman, and pytest documentation instead,
  and record that limitation in this plan.
- Commit only after the applicable gates have passed.

## Tolerances (exception triggers)

- Scope: if implementation requires changing more than five files, stop and
  ask for approval before continuing.
- Behaviour: if implementation would modify any file under `ansible/roles/` or
  `ansible/ansible_collections/`, stop and ask for approval.
- Playbook interface: if the compatibility rule cannot preserve the current
  `make site` or `make check` command contract, stop and present options.
- Dependencies: if validation requires adding `pytest-bdd`, `hypothesis`, a
  new Ansible collection, a new Molecule plugin, or another new dependency,
  stop and ask for approval.
- Validation: if `make check-fmt`, `make typecheck`, `make lint`, or
  `make test` fails after two fix attempts for reasons caused by this branch,
  stop and record the failing commands and logs.
- Documentation gates: if `make fmt`, `make markdownlint`, `make nixie`, or
  `git diff --check` fails for unrelated pre-existing files, record the exact
  failure and stop unless the fix is both obvious and within the file scope
  above.
- CodeRabbit: if `coderabbit review --agent` reports concerns that are within
  the approved planning scope, resolve them before the next milestone. If it
  asks for implementation beyond the approved plan, record the concern and ask
  the user before acting.
- Ambiguity: if two valid compatibility rules would materially change when a
  local role can switch to a collection role, stop and ask the user to choose.

## Risks

- Risk: The existing ADR already states that extracted roles must preserve
  `make site` and `make check`, but the statement may remain too terse to guide
  later role switches. Severity: high. Likelihood: high. Mitigation: turn the
  terse statement into an operational rule that names the preserved commands,
  acceptable deltas, validation evidence, and decision path for deliberate
  behaviour changes.

- Risk: A documentation-only roadmap item could grow into premature role
  extraction work. Severity: high. Likelihood: medium. Mitigation: keep
  `ansible/roles/`, `ansible/ansible_collections/`, and `ansible/site.yml` out
  of scope except as read-only evidence.

- Risk: `pytest-bdd`, Hypothesis, Molecule, and end-to-end testing guidance in
  the request could be applied mechanically even though this milestone changes
  no executable playbook behaviour. Severity: medium. Likelihood: medium.
  Mitigation: document why those tools are not applicable for item 1.1.2 unless
  implementation adds executable code or role behaviour, while still running
  the requested repository gates.

- Risk: The compatibility rule could be written in the users' guide as if users
  need a new command. Severity: medium. Likelihood: medium. Mitigation: keep
  the users' guide focused on the existing `make site` and `make check`
  commands and place contributor-facing criteria for switching in the
  developers' guide and ADR.

- Risk: External Ansible and Molecule guidance may drift over time.
  Severity: low. Likelihood: medium. Mitigation: cite official documentation
  only for stable concepts such as collection structure, role argument
  specifications, check mode, and Molecule scenarios, and avoid encoding
  tool-version claims that are not needed for this documentation-only item.

- Risk: `docs/falcon-correlation-id-middleware-design.md` is absent, so this
  plan cannot signpost its contents. Severity: low. Likelihood: high.
  Mitigation: record the absence in `Surprises & Discoveries` and do not rely
  on it as implementation evidence.

## Progress

- [x] (2026-05-18T22:47:00Z) Loaded the `leta`, `execplans`,
  `firecrawl-mcp`, `commit-message`, `pr-creation`, and `en-gb-oxendict-style`
  skills relevant to this planning activity.
- [x] (2026-05-18T22:47:00Z) Created the Leta workspace for this repository
  with `leta workspace add`.
- [x] (2026-05-18T22:47:00Z) Renamed the branch to
  `1-1-2-document-the-compatibility-rule-for-extracted-roles`.
- [x] (2026-05-18T22:47:00Z) Used a Wyvern agent team for read-only
  reconnaissance of roadmap, documentation, Makefile, Ansible, pytest, and
  Molecule context.
- [x] (2026-05-18T22:47:00Z) Started Firecrawl research into Ansible
  collection, role contract, Molecule, Podman, and testing prior art.
- [x] (2026-05-18T22:49:00Z) Completed Firecrawl research and folded stable
  source references into this ExecPlan.
- [x] (2026-05-18T22:49:00Z) Completed the initial ExecPlan draft with
  repository evidence and Firecrawl source references.
- [x] (2026-05-18T22:58:00Z) Ran direct Markdown validation for this ExecPlan
  with `markdownlint-cli2` and `git diff --check`; both passed.
- [x] (2026-05-18T22:58:00Z) Ran `make check-fmt`, `make typecheck`, and
  `make lint`; all passed.
- [x] (2026-05-18T22:58:00Z) Ran `make test`; the first run exposed an
  environment-sensitive pre-existing failure from `BASH_ENV`, and rerunning as
  `BASH_ENV= make test` passed.
- [x] (2026-05-18T22:58:00Z) Ran `make nixie`; it passed.
- [x] (2026-05-18T22:58:00Z) Recorded the unrelated `make fmt` and
  `make markdownlint` failures in `Surprises & Discoveries`.
- [x] (2026-05-18T23:03:00Z) Ran `coderabbit review --agent` and resolved its
  three in-scope prose findings.
- [x] (2026-05-18T23:05:00Z) Committed the planning artefact for review.
- [x] (2026-05-18T23:05:00Z) Pushed the branch to
  `origin/1-1-2-document-the-compatibility-rule-for-extracted-roles` and set
  upstream tracking.
- [x] (2026-05-18T23:06:00Z) Opened draft pull request
  `https://github.com/leynos/dev-env-rocky/pull/32` for the
  pre-implementation ExecPlan.

## Surprises & discoveries

- Observation: The requested "ansible testing" skill is not present under
  `/home/leynos/.codex/skills`. Evidence: searching skill names for `ansible`
  and `molecule` returned no files. Impact: this plan uses repository
  documentation and Makefile targets for Ansible, Molecule, Podman, pytest, and
  pytest-bdd guidance instead of a separate skill.

- Observation: `docs/falcon-correlation-id-middleware-design.md` is absent
  from this checkout. Evidence: listing `docs/` shows ADRs, guides, the
  roadmap, execplans, and complexity documentation, but not the named file.
  Impact: the plan records the absence and avoids citing that document as
  current repository truth.

- Observation: `pytest-bdd` is not currently wired into the repository.
  Evidence: the Wyvern test reconnaissance found no dependency or code
  reference beyond documentation notes for non-applicable milestones. Impact:
  implementation should not add pytest-bdd for this documentation-only item
  unless an approved scope change adds behaviour-level tests.

- Observation: `packaging.tools` has collection metadata and module tests but
  no collection `README.md`. Evidence: the collection contains `galaxy.yml`,
  `plugins/`, and `tests/`, while `agentic.agent_configs` also contains
  `README.md`. Impact: this provides useful downstream context for roadmap
  items 1.1.3 and 1.2, but it is outside the implementation scope for item
  1.1.2.

- Observation: `make fmt` is currently blocked by unrelated Markdown lint
  failures outside the ExecPlan scope because `mdformat-all` walks the wider
  tree before failing. Evidence:
  `/tmp/dev-env-rocky-1-1-2-document-the-compatibility-rule-for-extracted-roles-fmt.out`
  reports existing issues in `agent-prompts/`, `agent-skills/`, and several
  existing `docs/*.md` files. Impact: this plan file was validated directly
  with `markdownlint-cli2`, and formatter churn in unrelated files was
  reversed.

- Observation: `make markdownlint` is blocked by an unrelated existing
  blank-line issue in `docs/users-guide.md`. Evidence:
  `/tmp/dev-env-rocky-1-1-2-document-the-compatibility-rule-for-extracted-roles-markdownlint.out`
  reports `docs/users-guide.md:132` for `MD012/no-multiple-blanks`. Impact:
  the pre-approval planning branch does not modify that user guide line; direct
  linting of the new ExecPlan passes.

- Observation: `make test` depends on a clean non-interactive Bash environment
  for `tests/test_bootstrap_common.py`. Evidence: the first
  `/tmp/dev-env-rocky-1-1-2-document-the-compatibility-rule-for-extracted-roles-test.out`
  run failed because this session's `BASH_ENV` injected
  `/home/leynos/.lody/bin` into `PATH`; the rerun recorded in
  `/tmp/dev-env-rocky-1-1-2-document-the-compatibility-rule-for-extracted-roles-test-bash-env-empty.out`
  passed with `BASH_ENV=`. Impact: no code change is needed for the ExecPlan;
  implementation validation should run `BASH_ENV= make test` unless the
  environment is already clean.

## Decision log

- Decision: keep roadmap item 1.1.2 documentation-only unless the user approves
  implementation scope changes. Rationale: the roadmap asks for a written
  compatibility rule, and moving role tasks before the rule exists would
  undercut the phase ordering. Date/Author: 2026-05-18T22:47:00Z / Codex.

- Decision: place the operational rule in `docs/developers-guide.md`, keep the
  normative decision in `docs/adr-002-collection-boundary.md`, and mention only
  user-visible command stability in `docs/users-guide.md`. Rationale:
  contributors need criteria for switching; users need to know whether commands
  and generated files changed; the ADR records the accepted boundary.
  Date/Author: 2026-05-18T22:47:00Z / Codex.

- Decision: use lightweight pytest documentation checks only if they protect
  the rule without brittle prose matching. Rationale: item 1.1.2 has no
  executable playbook change, so behavioural, Molecule, end-to-end, and
  property tests do not add useful signal unless the implementation scope
  changes. Date/Author: 2026-05-18T22:47:00Z / Codex.

## Outcomes & retrospective

This section is intentionally blank while the plan is in draft. Update it after
implementation milestones and again when roadmap item 1.1.2 is complete.

## Relevant documentation and skills

Use these repository documents as source material:

- `docs/roadmap.md`, especially roadmap item 1.1.2 under "Record the
  role-collection boundary".
- `docs/adr-002-collection-boundary.md`, especially the existing consequence
  that extracted roles must preserve `make site` and `make check` behaviour.
- `docs/developers-guide.md`, especially "Collection Boundary", "Validation",
  "Firecrawl MCP", "Factory Droid Custom Models", and the role-specific
  sections.
- `docs/users-guide.md`, especially the opening playbook command guidance,
  "Agent Configuration", and "Firecrawl MCP".
- `docs/documentation-style-guide.md` for prose style and secret-handling
  rules.
- `docs/complexity-antipatterns-and-refactoring-strategies.md` for the
  complexity rationale against broad role relocation.
- `ansible/site.yml`, because current role order is part of the behaviour that
  extraction must preserve.
- `Makefile`, especially `site`, `check`, `molecule`, `test`, `lint`,
  `typecheck`, `check-fmt`, `markdownlint`, and `nixie`.
- `tests/test_agent_tools_role.py`, `tests/test_uv_tools_role.py`,
  `tests/test_node_packages_role.py`, `tests/test_coderabbit_cli_role.py`, and
  related tests under `tests/` as examples of static role regression checks.
- `ansible/roles/*/molecule/rocky10/` as examples of Molecule scenarios using
  Podman for role-level validation.

Use these skills and tools:

- `execplans`, for keeping this document self-contained and current.
- `leta`, for symbol-level code navigation if implementation unexpectedly
  touches Python or Ansible module code.
- `firecrawl-mcp`, to resolve gaps in external Ansible, Molecule, Podman, and
  testing prior art.
- `commit-message`, for file-based Git commit messages.
- `pr-creation` and `en-gb-oxendict-style`, for the draft pull request title
  and body.
- A Wyvern agent team, for bounded read-only planning reconnaissance. The
  sub-agents must not edit files or run tests.

## External prior art

Firecrawl research on 2026-05-18 found these stable planning implications:

- Ansible's role-to-collection migration guidance requires collection roles to
  follow collection layout and naming rules, use fully qualified collection
  names where needed, and move plugins into collection plugin directories
  rather than embedding them inside roles. Source:
  `https://docs.ansible.com/projects/ansible/latest/dev_guide/migrating_roles.html`.
- Ansible collection documentation defines the collection packaging surface
  that extracted roles will eventually live under. Source:
  `https://docs.ansible.com/projects/ansible/latest/collections_guide/index.html`.
- Ansible role reuse and role argument specification documentation support the
  later variable contract work in roadmap item 1.1.3. Sources:
  `https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_reuse_roles.html`
   and
  `https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_reuse_roles.html#role-argument-validation`.
- Ansible check mode and diff mode are the upstream behaviours behind this
  repository's `make check` command. Source:
  `https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_checkmode.html`.
- Ansible variable precedence guidance supports keeping site-local defaults,
  vaulted secret names, and host enablement policy out of reusable collection
  roles until their contract is explicit. Source:
  `https://docs.ansible.com/projects/ansible/latest/reference_appendices/general_precedence.html`.
- Molecule's playbook-oriented scenario documentation supports the later role
  execution harness in roadmap item 1.2.1, while this roadmap item remains
  documentation-only. Source:
  `https://docs.ansible.com/projects/molecule/getting-started-playbooks/`.
- Molecule v6 no longer treats pytest as a built-in verifier; Ansible-native
  verifier playbooks are the preferred Molecule verification path. Source:
  `https://github.com/ansible/molecule/issues/3920`.
- Ansible collection testing documentation identifies `ansible-test` sanity,
  unit, and integration tests as release-oriented collection validation. This
  informs later collection-role gates but does not expand item 1.1.2. Source:
  `https://docs.ansible.com/projects/ansible/latest/dev_guide/developing_collections_testing.html`.
- pytest remains useful for lightweight repository tests when a documentation
  invariant needs protection. Source: `https://docs.pytest.org/`.

Firecrawl also found community references to `pytest-ansible`, testinfra,
ansible-lint profiles, and Red Hat Molecule-with-Podman articles. Treat those
as optional downstream context, not as normative requirements for this
documentation-only item.

## Context and orientation

`Makefile` defines the user-facing playbook commands. `make site` runs
`ansible-playbook -i ansible/inventory.ini ansible/site.yml` with local
collection, library, module utility, and Ansible configuration paths.
`make check` runs the same playbook with `--check --diff`. These two commands
are the compatibility baseline named in roadmap item 1.1.2.

`ansible/site.yml` currently has a root-managed `servers` play for `system`,
`packages`, `infra_tools`, `user`, and `user_linger`, followed by an owner-user
play for `git`, `rustup`, `rust_crates`, `uv_tools`, `node_packages`,
`go_packages`, `paths`, `cursor_cli`, `coderabbit_cli`, `agent_tools`,
`sccache_user`, optional `rust_cleanup`, and `weave`. Role ordering is part of
the managed-host behaviour because later roles depend on earlier installed
tools, paths, users, and secrets.

`docs/adr-002-collection-boundary.md` already accepts the boundary between
reusable collection behaviour and site-local orchestration. Its current
compatibility statement is correct but brief. Implementation should expand or
cross-reference it so later contributors know the rule is operational: a local
role call may switch to a collection role only when the same commands still
produce equivalent host outcomes and check-mode diffs, with any intentional
behaviour change separately documented and accepted.

`docs/developers-guide.md` is the right place for contributor-facing practice.
It should tell a maintainer what evidence is required before replacing a local
role call with a collection role call. `docs/users-guide.md` is the right place
to keep users informed that extraction work does not change the commands they
run unless a later item explicitly documents that change.

Existing tests under `tests/` use pytest to protect role task definitions and
documentation contracts. Existing Molecule scenarios under
`ansible/roles/*/molecule/rocky10/` use Podman and Rocky Linux 10 containers
for role execution tests. Those are important examples for later roadmap items,
but item 1.1.2 should not create role execution scaffolding; that belongs to
roadmap item 1.2.1.

## Plan of work

Stage A is evidence lock-in. Reread this ExecPlan, `docs/roadmap.md`,
`docs/adr-002-collection-boundary.md`, `docs/developers-guide.md`,
`docs/users-guide.md`, `Makefile`, and `ansible/site.yml`. Confirm the branch
is `1-1-2-document-the-compatibility-rule-for-extracted-roles`. Confirm the
working tree contains only the approved plan changes before implementation
starts. If any other local edits appear, inspect them and do not revert them.
If they affect this task, record the conflict and ask the user how to proceed.

Stage B is tests-first documentation protection. Decide whether a focused
pytest test can protect the compatibility rule without brittle full-sentence
matching. A good test would assert that the developers' guide names
`make site`, `make check`, `ansible/site.yml`, and
`docs/adr-002-collection-boundary.md` in the extraction compatibility section.
If this can be implemented in one existing `tests/test_*` file without new
dependencies, add the failing test first and run the focused pytest command
through `tee`. If it would become brittle or exceed the file-scope tolerance,
record the decision not to add it and keep validation to Markdown and existing
repository gates.

Stage C is the compatibility-rule documentation. Update
`docs/adr-002-collection-boundary.md` so the existing consequence points to an
explicit compatibility rule instead of remaining a terse principle. Update
`docs/developers-guide.md` with a subsection under "Collection Boundary" that
states the switch rule in contributor language:

- preserve `make site` host outcomes for the current managed-host profile;
- preserve `make check` dry-run and diff expectations, except for reviewed and
  documented intentional deltas;
- preserve `ansible/site.yml` ordering semantics unless a later accepted
  decision changes them;
- prove the role with the relevant pytest, Molecule, `make check`, and
  documentation gates before changing the playbook call; and
- keep site-local wrappers when owner-specific defaults, private repositories,
  vaulted secret names, or host enablement policy remain in the site.

Update `docs/users-guide.md` only if a user-facing note is needed to say that
the current extraction rule does not change the commands users run. Avoid
adding implementation mechanics that belong in the developers' guide.

Stage D is roadmap and review preparation. After the documentation and any
small tests pass, update `docs/roadmap.md` item 1.1.2 from unchecked to checked
and link it to the compatibility rule or ADR. Do not mark roadmap item 1.2.1 or
later tasks as done. Run `coderabbit review --agent` and clear all in-scope
concerns before committing. If CodeRabbit raises concerns that require role
movement or new dependencies, record them in this ExecPlan and ask the user
before expanding scope.

Stage E is branch publication. Commit the plan or approved implementation with
a file-based commit message. Push the branch to
`origin/1-1-2-document-the-compatibility-rule-for-extracted-roles` and set the
upstream. Create a draft pull request whose title includes `(1.1.2)`, whose
summary links to this ExecPlan, and whose final `## References` section includes
the Lody session link built from `${LODY_SESSION_ID}`.

## Concrete steps

All commands run from the repository root:

```bash
cd /home/leynos/.lody/repos/github---leynos---dev-env-rocky/worktrees/dab5bba6-4b60-4cc6-9e35-af27862b3af1
```

Confirm branch and working tree:

```bash
git branch --show-current
git status --short --branch
```

Expected branch:

```plaintext
1-1-2-document-the-compatibility-rule-for-extracted-roles
```

Use a stable log prefix for gates:

```bash
BRANCH=$(git branch --show-current)
PROJECT=$(basename "$(git rev-parse --show-toplevel)")
LOG_PREFIX="/tmp/${PROJECT}-${BRANCH}"
```

If adding a focused pytest documentation test, run it before implementation and
expect it to fail for the missing rule:

```bash
UV_CACHE_DIR=.uv-cache uv run --with pytest --with pyyaml \
  pytest -q tests/test_documentation_contracts.py \
  2>&1 | tee "${LOG_PREFIX}-doc-contract-red.out"
```

After implementing approved changes, run gates sequentially:

```bash
make fmt 2>&1 | tee "${LOG_PREFIX}-fmt.out"
make check-fmt 2>&1 | tee "${LOG_PREFIX}-check-fmt.out"
make typecheck 2>&1 | tee "${LOG_PREFIX}-typecheck.out"
make lint 2>&1 | tee "${LOG_PREFIX}-lint.out"
make test 2>&1 | tee "${LOG_PREFIX}-test.out"
make markdownlint 2>&1 | tee "${LOG_PREFIX}-markdownlint.out"
make nixie 2>&1 | tee "${LOG_PREFIX}-nixie.out"
git diff --check 2>&1 | tee "${LOG_PREFIX}-diff-check.out"
```

Run the playbook syntax and dry-run gates if the approved implementation edits
Ansible-facing documentation in a way that claims command compatibility:

```bash
COLLECTIONS=./ansible/ansible_collections
PACKAGING_MODULES="${COLLECTIONS}/packaging/tools/plugins/modules"
AGENT_MODULES="${COLLECTIONS}/agentic/agent_configs/plugins/modules"
AGENT_UTILS="${COLLECTIONS}/agentic/agent_configs/plugins/module_utils"
ANSIBLE_CONFIG=./ansible/ansible.cfg \
ANSIBLE_COLLECTIONS_PATH="${COLLECTIONS}" \
ANSIBLE_LIBRARY="${PACKAGING_MODULES}:${AGENT_MODULES}" \
ANSIBLE_MODULE_UTILS="${AGENT_UTILS}" \
ansible-playbook -i ansible/inventory.ini ansible/site.yml --syntax-check \
  2>&1 | tee "${LOG_PREFIX}-ansible-syntax.out"

make check 2>&1 | tee "${LOG_PREFIX}-make-check.out"
```

Run Molecule only if implementation changes role behaviour or the approved
documentation claims new role-level validation behaviour:

```bash
MOLECULE='uv run --with ansible-core --with molecule'
MOLECULE="${MOLECULE} --with molecule-plugins[podman] molecule" \
make molecule 2>&1 | tee "${LOG_PREFIX}-molecule.out"
```

Run CodeRabbit after the major documentation milestone:

```bash
coderabbit review --agent 2>&1 | tee "${LOG_PREFIX}-coderabbit.out"
```

Commit with a file-based message:

```bash
COMMIT_MSG_DIR=$(mktemp -d)
cat > "${COMMIT_MSG_DIR}/COMMIT_MSG.md" << 'ENDOFMSG'
Document extracted-role compatibility plan

Add the pre-implementation ExecPlan for roadmap item 1.1.2 so the
compatibility rule can be reviewed before documentation changes land.
ENDOFMSG
git add docs/execplans/1-1-2-document-the-compatibility-rule-for-extracted-roles.md
git commit -F "${COMMIT_MSG_DIR}/COMMIT_MSG.md"
rm -rf "${COMMIT_MSG_DIR}"
```

Publish and open the draft pull request:

```bash
git push -u origin 1-1-2-document-the-compatibility-rule-for-extracted-roles
echo "${LODY_SESSION_ID}"
```

The pull request title must include `(1.1.2)`. The body must mention this
ExecPlan in the summary and end with:

```markdown
## References

- Lody session: https://lody.ai/leynos/sessions/${LODY_SESSION_ID}
```

## Validation and acceptance

The initial planning branch is acceptable when:

- `docs/execplans/1-1-2-document-the-compatibility-rule-for-extracted-roles.md`
  exists, is self-contained, and has `Status: DRAFT`.
- The plan signposts `docs/roadmap.md`,
  `docs/adr-002-collection-boundary.md`, `docs/developers-guide.md`,
  `docs/users-guide.md`, `docs/documentation-style-guide.md`,
  `docs/complexity-antipatterns-and-refactoring-strategies.md`, `Makefile`,
  `ansible/site.yml`, Leta, Firecrawl, Wyvern agents, and the relevant Git and
  PR skills.
- The plan states that implementation must wait for explicit user approval.
- The plan describes how implementation will validate unit tests with pytest,
  why pytest-bdd, Hypothesis, end-to-end, and Molecule tests are not directly
  applicable unless executable behaviour changes, and when Molecule with Podman
  becomes required.
- `make check-fmt`, `make typecheck`, `make lint`, `make test`,
  `make markdownlint`, `make nixie`, and `git diff --check` pass for the
  planning branch, or any unrelated failure is recorded here before stopping.
- `coderabbit review --agent` reports no unresolved in-scope concerns.
- The branch tracks
  `origin/1-1-2-document-the-compatibility-rule-for-extracted-roles`.
- A draft pull request exists with `(1.1.2)` in the title, this ExecPlan linked
  in the summary, and a `## References` section containing the Lody session URL.

The later implementation is acceptable only after user approval and when:

- the compatibility rule is explicit in contributor-facing documentation;
- the ADR or developers' guide states when `ansible/site.yml` may switch from a
  local role to a collection role;
- the users' guide still accurately describes the `make site` and `make check`
  commands;
- roadmap item 1.1.2 is checked off and linked to the rule; and
- all required gates for the approved implementation pass.

## Idempotence and recovery

The documentation edits are ordinary text changes and are safe to repeat. If
formatting changes line wrapping, rerun `make fmt` and then rerun the gates
sequentially. Do not use `git reset --hard` or `git checkout --` to recover
from mistakes because the working tree may contain user changes. Use
`git diff`, `git status --short`, and targeted `apply_patch` edits instead.

If a gate fails because of this branch, inspect the matching `/tmp` log, make a
minimal fix, update this ExecPlan's `Progress` or `Surprises & Discoveries`,
and rerun the failed gate before continuing. If a gate fails for unrelated
pre-existing reasons, stop and report the command, log path, and failing files
to the user.

If the draft pull request already exists when publication starts, do not create
a duplicate. Read the existing pull request state and update its title and body
while preserving its draft or ready-for-review state.

## Artifacts and notes

Wyvern reconnaissance for roadmap and documentation found that ADR-002 already
contains the terse compatibility line:

```plaintext
Extracted roles must preserve current `make site` and `make check` behaviour
until a later decision deliberately changes the managed-host profile.
```

That wording is directionally correct. The implementation should make it
operational enough for later tasks to decide when a role switch is allowed.

Wyvern reconnaissance for Ansible testing found existing Molecule `rocky10`
scenarios for `uv_tools`, `node_packages`, `paths`, and `coderabbit_cli`. These
use the Podman driver and Rocky Linux 10 image. It also found no current
pytest-bdd wiring.

Firecrawl research completed before commit. The stable source implications are
recorded in "External prior art". The most relevant result for this plan is
that Ansible's own migration documentation reinforces the need to preserve
collection layout, fully qualified names, plugin placement, check mode, and
variable precedence rules when local roles eventually move into collections.

## Interfaces and dependencies

This roadmap item should not add runtime interfaces or dependencies. The
compatibility rule should name existing interfaces only:

- `make site`, the command that applies `ansible/site.yml` to the inventory.
- `make check`, the command that runs the same playbook with `--check --diff`.
- `ansible/site.yml`, the site-local orchestration surface whose role order is
  part of the current managed-host behaviour.
- `docs/adr-002-collection-boundary.md`, the accepted boundary decision.
- `docs/developers-guide.md`, the contributor-facing practice document.
- `docs/users-guide.md`, the user-facing playbook behaviour document.
- pytest, for repository-level static and unit checks when useful.
- Molecule with Podman, for later role execution tests when role behaviour
  changes.

No new Ansible role defaults, argument specifications, Python modules,
packages, or collection metadata should be introduced for item 1.1.2.

## Revision note

- 2026-05-18T22:47:00Z: Created the initial draft plan for roadmap item 1.1.2.
  This establishes the compatibility-rule implementation path and keeps actual
  documentation changes behind the required user approval gate.
- 2026-05-18T23:06:00Z: Updated progress after publishing the draft pull
  request. This does not approve implementation; it records that the plan is
  ready for review.
