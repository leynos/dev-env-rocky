# Fix managed user bin directory precedence

This ExecPlan (execution plan) is a living document. The sections `Constraints`,
 `Tolerances`, `Risks`, `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Status: BLOCKED

## Purpose / big picture

The managed user shell environment on `vendetta.df12.net` and `rohga.df12.net`
should prefer commands in `~/.local/bin` over commands installed by Bun in
`~/.bun/bin`, while still keeping Bun commands available. This matters because
the local workstation showed a concrete failure mode: `claude` resolved to
`~/.bun/bin/claude`, that wrapper failed, and the working native Claude Code
launcher in `~/.local/bin/claude` was hidden behind it.

The fix should make the managed PATH order deterministic for the owner user on
both inventory hosts. After the change, a fresh owner-user login shell should
show the managed prefix in this order:

```plaintext
/home/leynos/.local/bin:/home/leynos/.cargo/bin:/home/leynos/.bun/bin:/home/leynos/go/bin
```

The exact `claude` executable selected on the hosts depends on which launcher
exists. Today neither host has `/home/leynos/.local/bin/claude`, so `claude`
still resolves to `/home/leynos/.bun/bin/claude` and works there. The important
behaviour is that if a native Claude launcher is installed later in
`~/.local/bin`, it will take precedence without manual profile surgery.

## Constraints

- Scope the operational fix to the managed hosts in `ansible/inventory.ini`:
  `vendetta.df12.net` and `rohga.df12.net`. The user wrote `rogha`; the
  repository and inventory use `rohga.df12.net`.
- Do not remove Bun or stop installing Bun-managed packages. Bun global
  commands must remain available through `~/.bun/bin`.
- Do not delete non-managed profile content such as legacy Bun installer blocks
  unless the user explicitly approves that cleanup. The plan may add a managed
  block after them.
- Keep the owner user as `owner_user` from Ansible variables. Do not hardcode
  `leynos` inside role code except in validation commands and recorded evidence.
- Prefer Makefile targets over raw command suites for validation and
  deployment. Use `tee` logs for gates and host checks.
- Do not start implementation until this draft is approved.

## Tolerances (exception triggers)

- Scope: if the fix requires touching more than six repository files, stop and
  explain why the blast radius expanded.
- Profiles: if implementation requires deleting arbitrary user profile lines
  on `vendetta.df12.net` or `rohga.df12.net`, stop and request approval.
- Interfaces: if the `paths` role needs a new public variable or a changed
  `ansible/site.yml` role order, stop and document the trade-off first.
- Dependencies: if a new Python, Ansible, or shell dependency is needed, stop
  and request approval.
- Host access: if either target host is unreachable or `make site` cannot apply
  to both hosts, stop after recording which host failed and why.
- Iterations: if the focused tests or host PATH checks fail after two fix
  attempts, stop and update this plan with the observed failures.

## Risks

- Risk: Login profiles source files in different orders on different shells.
  Severity: medium. Likelihood: medium. Mitigation: validate with
  `sudo -iu {{ owner_user }} bash -lc ...` on both hosts, because that
  reproduces the owner-user login path used during the investigation.

- Risk: Existing `~/.bash_profile` files contain repeated Bun installer blocks
  that run after `.bashrc`. Severity: high. Likelihood: high. Mitigation: add
  an Ansible-managed EOF block in `.bash_profile` that re-sources the managed
  path normaliser after legacy profile content, instead of deleting the legacy
  blocks.

- Risk: The current path helper only skips existing entries, so it cannot move
  an existing `~/.local/bin` entry ahead of `~/.bun/bin`. Severity: high.
  Likelihood: high. Mitigation: replace skip-only path handling with a
  normalising helper that removes managed entries from `PATH` and then re-adds
  them once in the desired order.

- Risk: `bin/setup-paths` and `ansible/roles/paths/templates/00-paths.j2`
  drift apart. Severity: medium. Likelihood: medium. Mitigation: update both
  generated shell templates in the same commit and add focused tests that
  exercise the normalisation behaviour.

## Progress

- [x] 2026-05-08 13:41 BST: Confirmed the local failure mode. The current
  shell resolves `claude` to `/home/leynos/.bun/bin/claude`, that wrapper
  fails, and `/home/leynos/.local/bin/claude --version` succeeds with
  `2.1.34 (Claude Code)`.
- [x] 2026-05-08 13:41 BST: Confirmed that a local-first candidate PATH
  resolves `claude` to `/home/leynos/.local/bin/claude` and runs successfully.
- [x] 2026-05-08 13:41 BST: Checked `vendetta.df12.net` and
  `rohga.df12.net`. On both hosts, `claude` currently resolves to
  `/home/leynos/.bun/bin/claude` and works. Neither host currently has
  `/home/leynos/.local/bin/claude`.
- [x] 2026-05-08 13:41 BST: Confirmed both hosts have PATH order drift and
  repeated Bun path prepends in login profiles. `vendetta.df12.net` reports
  `2.1.96 (Claude Code)` from Bun; `rohga.df12.net` reports
  `2.1.119 (Claude Code)` from Bun.
- [x] 2026-05-08 13:41 BST: Confirmed the repository path template reproduces
  the ordering bug when sourced with a contaminated PATH. With `.bun/bin` and
  `.local/bin` already present, it outputs
  `/home/leynos/go/bin:/home/leynos/.cargo/bin:/home/leynos/.bun/bin:/home/leynos/.local/bin:...`.
- [x] 2026-05-08 13:59 BST: Added focused regression tests in
  `tests/test_paths_role.py`. The initial focused run failed as expected
  because the template left `.bun/bin` ahead of `.local/bin`, `setup-paths`
  still generated skip-only logic, and the `.bash_profile` EOF hook did not
  exist.
- [x] 2026-05-08 14:02 BST: Updated the path template and local `setup-paths`
  generator to remove duplicate managed entries before prepending each managed
  directory once in the documented order.
- [x] 2026-05-08 14:02 BST: Added a managed `.bash_profile` EOF hook so the
  normaliser runs after legacy Bun installer blocks.
- [x] 2026-05-08 14:03 BST: Re-ran the focused tests with
  `UV_CACHE_DIR=.uv-cache UV_TOOL_DIR=.uv-tools uv run --with pytest pytest -v tests/test_paths_role.py`;
  all three focused tests passed.
- [x] 2026-05-08 14:08 BST: Ran `make fmt`; Python formatting and import
  sorting succeeded, but `mdformat-all` failed on pre-existing Markdown issues
  in `agent-prompts/` and `agent-skills/`. Reverted unrelated formatter rewrites
  and kept only task-scoped files.
- [x] 2026-05-08 14:10 BST: Ran local gates successfully:
  `make check-fmt`, `make lint`, `make typecheck`, `make test`,
  `make markdownlint`, `make nixie`, and `git diff --check`.
- [ ] Apply the role to `vendetta.df12.net` and `rohga.df12.net`. Blocked:
  `make site` failed before reaching the `paths` role because
  `node_packages` treats `bun pm trust @zed-industries/codex-acp-linux-x64`
  returning "0 scripts ran" as fatal on both hosts.
- [ ] Verify login-shell PATH and `claude` resolution on both hosts.

## Surprises & Discoveries

- The original local caveat is valid on this machine, but the same immediate
  `claude` failure does not reproduce on the two managed hosts. Their Bun
  launchers work today.
- During implementation, `grepai workspace status Projects` confirmed that the
  `dev-env-rocky` project is registered, but semantic searches failed because
  the local Qdrant endpoint at `127.0.0.1:6334` refused connections. Exact
  repository reads are being used as the fallback.
- The two managed hosts do not have `/home/leynos/.local/bin/claude`, so PATH
  precedence cannot currently make them choose a native Claude launcher.
- Both managed hosts have legacy Bun installer blocks in `~/.bash_profile` that
  run after `.bashrc` is sourced. This means fixing only `~/.bashrc.d/00-paths`
  is not enough for login shells unless the normaliser also runs at the end of
  `.bash_profile`.
- `vendetta.df12.net` has an extra `export PATH=/root/.bun/bin:${PATH}` line in
  `~/.bashrc`. The plan should avoid deleting it automatically, but the final
  normaliser must make it harmless for managed user bin precedence.
- Running `bin/setup-paths` inside a test needed the inherited tool PATH so its
  `/usr/bin/env -S uv run --script` shebang can find `uv`; the test still
  overwrites `PATH` before sourcing the generated file to keep the
  normalisation assertion deterministic.
- `make fmt` still scans Markdown outside the Makefile's `MARKDOWN_PATHS` list
  through `mdformat-all` and fails on unrelated prompt/skill files. The focused
  Markdown gate, `make markdownlint`, passes for the repository's declared
  Markdown gate set.
- `make site` did not reach `go_packages`, `paths`, `cursor_cli`,
  `agent_tools`, `sccache_user`, `rust_cleanup`, or `weave`. The failure
  occurred in `node_packages` for both hosts after earlier roles had already
  made unrelated package-tool updates.

## Decision Log

- Decision: Treat this as a deterministic PATH normalisation bug, not as a
  Claude Code package installation bug on the managed hosts. Rationale: The Bun
  Claude launchers on both hosts work, but PATH order is still unstable and
  contrary to the intended local-first contract.

- Decision: Keep the desired managed order as
  `~/.local/bin`, `~/.cargo/bin`, `~/.bun/bin`, `~/go/bin`. Rationale:
  `docs/users-guide.md` already documents that order for managed user
  environments, and it lets native or explicitly linked commands in
  `~/.local/bin` override package-manager shims.

- Decision: Add an EOF managed hook to `.bash_profile` instead of deleting
  repeated Bun installer blocks. Rationale: The legacy profile content is
  user-owned state. Re-running the normaliser at EOF fixes observable PATH
  order without destructive cleanup.

- Decision: Update `bin/setup-paths` together with the Ansible template.
  Rationale: `shiny-new-pc.sh` uses `bin/setup-paths` for local bootstrap, so
  leaving it with skip-only path handling would preserve the bug outside
  Ansible-managed hosts.

- Decision: Stop before using a narrower playbook invocation or hand-editing
  remote profile files. Rationale: the plan's host-apply tolerance says to stop
  if `make site` cannot apply to both hosts, and the approved apply path failed
  before the `paths` role.

## Outcomes & Retrospective

Implementation is committed locally in `a95b84e`, but host rollout is blocked.
Local tests prove the generated shell normalises contaminated PATH input into
the documented order, and all required local gates passed. The managed hosts
have not yet received the `paths` role update through the approved `make site`
apply path because `node_packages` failed first.

Options to unblock rollout:

- Fix `node_packages` so `bun pm trust` treats "0 scripts ran" as idempotent
  for packages that have no current postinstall script or are already trusted,
  then rerun `make site`.
- Temporarily disable trusted postinstall for
  `@zed-industries/codex-acp-linux-x64` if the package genuinely has no
  postinstall script to trust, then rerun `make site`.
- Approve a narrower Ansible invocation that runs only the `paths` role on the
  two hosts, accepting that this deviates from the plan's preferred full apply
  path.

## Implementation plan

First, add focused tests before changing the path logic. Create or extend tests
around the `paths` role and `bin/setup-paths` so they demonstrate the current
failure: when `PATH` already contains `~/.bun/bin` before `~/.local/bin`, the
generated `00-paths` script must still produce exactly one managed prefix in
the documented order. A representative assertion should prove that this input:

```plaintext
/home/example/.bun/bin:/home/example/.local/bin:/usr/bin
```

normalises to this prefix:

```plaintext
/home/example/.local/bin:/home/example/.cargo/bin:/home/example/.bun/bin:/home/example/go/bin:/usr/bin
```

The test should also assert that duplicate `~/.bun/bin` entries are collapsed
to one. Use the existing `tests/test_bootstrap_common.py` style: run Bash with
a temporary `HOME`, create the managed directories under that temporary home,
source the generated shell content, and inspect stdout. If testing the Jinja
template directly is awkward, render the relevant static shell through a small
test helper rather than invoking Ansible.

Second, update `ansible/roles/paths/templates/00-paths.j2`. Replace the current
`pathmunge` helper with a normalising helper that removes every occurrence of a
managed directory from `PATH`, then prepends that directory if it exists. Apply
the managed directories in reverse order so the final visible order is:

```plaintext
${HOME}/.local/bin
${HOME}/.cargo/bin
${HOME}/.bun/bin
${HOME}/go/bin
```

The shell should not use arrays, because it may be sourced by POSIX-ish profile
paths even though the user shell is Bash. A simple colon-splitting loop is
acceptable if it preserves unrelated entries and handles empty `PATH` safely.

Third, update `bin/setup-paths` so the generated local bootstrap file uses the
same normalising helper and directory order. Keep the script's existing Python
dependencies and command interface unchanged.

Fourth, update `ansible/roles/paths/tasks/main.yml` to ensure `.bash_profile`
sources the managed normaliser after any existing profile content. Use
`ansible.builtin.blockinfile` with a clearly named marker, append at EOF, and
source only `~/.bashrc.d/00-paths` if it exists. Do not remove existing Bun
installer blocks in this milestone. The managed block should be safe to run
more than once.

Fifth, update documentation if the implementation changes the user-visible
contract. At minimum, check `docs/users-guide.md` and confirm that its
documented PATH order remains correct. If the guide does not mention that the
role normalises duplicate managed entries, add one concise sentence.

Sixth, run local validation with logs:

```bash
set -o pipefail; make check-fmt 2>&1 | tee /tmp/check-fmt-dev-env-rocky-bun-trust.out
set -o pipefail; make lint 2>&1 | tee /tmp/lint-dev-env-rocky-bun-trust.out
set -o pipefail; make typecheck 2>&1 | tee /tmp/typecheck-dev-env-rocky-bun-trust.out
set -o pipefail; make test 2>&1 | tee /tmp/test-dev-env-rocky-bun-trust.out
set -o pipefail; make markdownlint 2>&1 | tee /tmp/markdownlint-dev-env-rocky-bun-trust.out
set -o pipefail; make nixie 2>&1 | tee /tmp/nixie-dev-env-rocky-bun-trust.out
git diff --check
```

If only Markdown changes occur after approval, the Python gates may be skipped
with a note. If the path role or tests change, run all Python and Markdown
gates listed above.

Seventh, apply the role to both hosts through the repository Makefile:

```bash
set -o pipefail; make site 2>&1 | tee /tmp/site-dev-env-rocky-bun-trust.out
```

If `make site` changes unrelated package state because the branch also contains
pending package role updates, record that in this plan before proceeding. Do
not hand-edit host profile files as a shortcut.

Finally, verify both hosts:

```bash
for host in vendetta.df12.net rohga.df12.net; do
  ssh -o StrictHostKeyChecking=accept-new root@"$host" \
    'sudo -iu leynos bash -lc '"'"'
      printf "PATH=%s\n" "$PATH"
      printf "claude=%s\n" "$(command -v claude || true)"
      type -a claude || true
      claude --version
    '"'"''
done
```

Acceptance is:

- The `PATH=` line begins with
  `/home/leynos/.local/bin:/home/leynos/.cargo/bin:/home/leynos/.bun/bin:/home/leynos/go/bin:`.
- `~/.bun/bin` appears only once in the managed prefix.
- `claude --version` exits 0 on both hosts.
- If `/home/leynos/.local/bin/claude` is absent, `claude` may still resolve to
  `/home/leynos/.bun/bin/claude`; if it is present, it must resolve to
  `/home/leynos/.local/bin/claude`.
