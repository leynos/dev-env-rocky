# Install CodeRabbit CLI

This ExecPlan (execution plan) is a living document. The sections
`Constraints`, `Tolerances`, `Risks`, `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work
proceeds.

Status: COMPLETE

## Purpose / big picture

After this change, running the repository's Ansible site playbook installs the
CodeRabbit CLI for the managed owner user on development hosts. The role uses
the already-downloaded installer script at
`ansible/roles/coderabbit_cli/files/coderabbit-install.sh`, keeps
host-specific CodeRabbit API keys in Ansible Vault, and proves the behaviour
with a Molecule scenario that runs on Podman against a Rocky Linux container.

Success is observable in three ways. The user role creates
`~/.local/bin/coderabbit` and the `~/.local/bin/cr` alias. The role
authenticates the CLI by running `coderabbit auth login --api-key` with the
host's vaulted key. Running `coderabbit review --agent` from the repository
after major milestones starts the installed CLI in agent mode.

## Constraints

The branch is `coderabbit-cli`. The plan file for this branch is
`docs/execplans/coderabbit-cli.md`.

Always read `AGENTS.md` before editing files in this repository. Use the
repository `Makefile` targets for gates where they exist. Gate commands must be
run sequentially with `tee` logs under `/tmp`; do not run format, lint, type
checking, tests, or Molecule in parallel.

Do not place build artefacts in `/tmp`; `/tmp` is only for logs and scratch
files. Do not create an isolated Cargo cache.

The CodeRabbit installer is already available at
`ansible/roles/coderabbit_cli/files/coderabbit-install.sh`.
Do not fetch a different installer for the role unless the checked-in script is
found to be unusable. The original installer source is
`https://cli.coderabbit.ai/install.sh`.

The API keys are local secret files at `~/__coderabbit_token_rohga` and
`~/__coderabbit_token_vendetta`. Store their values only through Ansible Vault
using the vault password file `~/.ansible_vault_pass`; do not commit plaintext
tokens.

The role must include end-to-end Molecule coverage using Podman. The scenario
must be deterministic and must not depend on reaching CodeRabbit's release
service during the container test.

Commit after each logical change and only after the relevant gates pass.

## Tolerances

Stop and ask for direction if the checked-in installer cannot be adapted to a
deterministic Molecule test without modifying the vendored installer script.

Stop and ask for direction if CodeRabbit authentication requires a file format
or command whose behaviour cannot be confirmed without exposing the secret
token in logs.

Stop if a gate requires more than 1200 seconds in one command. Split the gate
or report the blocker.

Stop if the disk or `/tmp` fills up.

## Risks

The installer normally downloads a release archive from CodeRabbit. Molecule
must avoid external network dependence by serving a local fake release archive
and pointing `CODERABBIT_DOWNLOAD_URL` at that local fixture.

The CodeRabbit CLI's exact authentication contract may change. Live help output
confirmed the current supported non-interactive path is
`coderabbit auth login --api-key <api-key>` for persistent authentication, or
`coderabbit review --agent --api-key <api-key>` for one review invocation.

The repository's `make molecule` target currently covers only `node_packages`
and `paths`. The target must be updated so the new `coderabbit_cli` scenario is
part of the normal role gate.

## Progress

- [x] 2026-05-10: Verified the branch is `coderabbit-cli` and the worktree was
  clean before starting.
- [x] 2026-05-10: Confirmed no existing `docs/execplans/coderabbit-cli.md`
  plan existed.
- [x] 2026-05-10: Read `AGENTS.md`, `Makefile`, the Cursor CLI role, existing
  Molecule role scenarios, the inventory, and current vault layout.
- [x] 2026-05-10: Confirmed the installer script exists at
  `ansible/roles/coderabbit_cli/files/coderabbit-install.sh` and installs
  `coderabbit` plus `cr` under
  `~/.local/bin`.
- [x] 2026-05-10: Added the `coderabbit_cli` role, wired it into
  `ansible/site.yml`, and added focused Python regression coverage.
- [x] 2026-05-10: Added deterministic Molecule coverage using a local fake
  CodeRabbit release archive served through `file:///tmp/coderabbit-releases`.
- [x] 2026-05-10: Added vaulted `coderabbit_api_keys` entries for
  `rohga.df12.net` and `vendetta.df12.net` from the provided token files in the
  source-of-truth vault file at
  `../../dev-env-rocky/ansible/group_vars/all/vault.yml`.
- [x] 2026-05-10: Updated `docs/users-guide.md` and
  `docs/developers-guide.md`.
- [x] 2026-05-10: Ran CodeRabbit review checkpoints. The unauthenticated run
  failed as expected, and the `--api-key` run reached the review service but
  failed because the CodeRabbit account has no usage credits.
- [x] 2026-05-10: Ran focused tests, full Python gates, Markdown/Mermaid gates,
  full Makefile Molecule coverage, vault verification, `git diff --check`, and
  `ansible-playbook --syntax-check` with durable logs under `/tmp`.
- [x] Commit the completed implementation change.
- [x] Commit each completed logical change.

## Surprises & Discoveries

GrepAI is configured for the `Projects` workspace, but Qdrant was not reachable
at `127.0.0.1:6334` during initial discovery. Exact file inspection was used as
the fallback.

The current `make molecule` target runs `node_packages` and `paths` only, so
the new role needs to be added there for the requested e2e coverage to be part
of the repository gate.

The existing Cursor CLI role is a close local pattern for a user-scoped CLI
installer role, but it fetches from the network during deployment. The
CodeRabbit role can avoid installer drift by copying and executing the
pre-downloaded installer script.

The bare Rocky 10 Molecule container lacks `git` and `unzip`, both of which the
CodeRabbit installer requires. The system package role already installed `git`,
but `unzip` had to be added there, and the Molecule prepare step installs both
tools in the container fixture.

`molecule` is not installed directly on `PATH` in this environment. Focused
Molecule validation was run with
`uv run --with molecule --with 'molecule-plugins[podman]' molecule test -s rocky10`.

`make fmt` failed on pre-existing Markdown lint issues outside the repository's
`MARKDOWN_PATHS` gate, under `agent-prompts` and `agent-skills`. The unrelated
formatter edits were reverted, and the relevant Markdown gate
`make markdownlint` passed.

The live CodeRabbit CLI did not accept `CODERABBIT_API_KEY` as an environment
variable for `coderabbit review --agent`. Its help output documents
`coderabbit auth login --api-key <api-key>` for stored authentication and
`coderabbit review --agent --api-key <key>` for direct review authentication,
so the role authenticates with `auth login --api-key`.

## Decision Log

2026-05-10: Use a dedicated `ansible/roles/coderabbit_cli` role instead of
folding the installer into `agent_tools`. This matches the existing
`cursor_cli` role boundary and keeps CLI installation separate from agent
configuration.

2026-05-10: Use Molecule's Podman driver with a Rocky Linux 10 container to
match existing role scenarios. The scenario will serve a local fake CodeRabbit
release archive, so the test proves the installer integration without relying on
the public release service.

2026-05-10: Store CodeRabbit tokens in a host-keyed `coderabbit_api_keys`
mapping in `../../dev-env-rocky/ansible/group_vars/all/vault.yml`, which is
the deployment source-of-truth vault file. This avoids committing host access
tokens to the branch, even as inline vault blocks.

2026-05-10: Authenticate CodeRabbit CLI with `coderabbit auth login --api-key`
rather than exporting `CODERABBIT_API_KEY` in shell startup files. This matches
the live CLI help output and avoids placing the secret in every interactive
shell environment.

## Implementation Plan

First, add the planning document and gate it with Markdown checks. Commit this
plan before making role changes.

Second, add `ansible/roles/coderabbit_cli`. The role creates
`{{ ansible_facts.env.HOME }}/.local/bin`, copies
`ansible/roles/coderabbit_cli/files/coderabbit-install.sh` to a temporary
managed location, runs it as the owner user with `CODERABBIT_INSTALL_DIR` set
to that bin directory, and declares
`creates: ~/.local/bin/coderabbit` for idempotence. It then runs
`coderabbit auth login --api-key` with `coderabbit_api_keys[inventory_hostname]`
and `no_log: true`, using `creates: ~/.coderabbit/auth.json` to avoid repeated
authentication.

Third, wire `coderabbit_cli` into the user-environment role list in
`ansible/site.yml` before `agent_tools`. Add Python regression tests that
assert the role uses the local installer path, remains idempotent, keeps
secret-bearing tasks under `no_log`, and runs before `agent_tools`.

Fourth, add a Molecule `rocky10` scenario under
`ansible/roles/coderabbit_cli/molecule/rocky10`. The prepare playbook creates a
fake CodeRabbit release directory containing `latest/VERSION` and a zip archive
with an executable fake `coderabbit`. Converge points `CODERABBIT_DOWNLOAD_URL`
at that local release fixture and passes a fake `coderabbit_api_keys` mapping.
Verify asserts the `coderabbit` binary, `cr` symlink, auth file, agent review
fixture, and idempotent second converge result.

Fifth, update `Makefile` so `make molecule` runs the new scenario. Update
`docs/users-guide.md` and `docs/developers-guide.md` to document the role,
secret rotation, and test strategy.

Sixth, use `ansible-vault encrypt_string` with
`--vault-password-file ~/.ansible_vault_pass` to add
`~/__coderabbit_token_rohga` and `~/__coderabbit_token_vendetta` to vault.

Finally, run focused and full gates with `tee` logs, run
`coderabbit review --agent` after major milestones, update this plan with
evidence, and commit each logical change after the relevant gates pass.

## Validation

Use these commands, with the branch name interpolated into the log path:

```bash
make markdownlint 2>&1 | tee /tmp/markdownlint-dev-env-rocky-coderabbit-cli.out
```

```bash
make nixie 2>&1 | tee /tmp/nixie-dev-env-rocky-coderabbit-cli.out
```

```bash
make check-fmt 2>&1 | tee /tmp/check-fmt-dev-env-rocky-coderabbit-cli.out
```

```bash
make lint 2>&1 | tee /tmp/lint-dev-env-rocky-coderabbit-cli.out
```

```bash
make typecheck 2>&1 | tee /tmp/typecheck-dev-env-rocky-coderabbit-cli.out
```

```bash
make test 2>&1 | tee /tmp/test-dev-env-rocky-coderabbit-cli.out
```

```bash
make molecule \
  MOLECULE="uv run --with molecule --with 'molecule-plugins[podman]' molecule" \
  2>&1 | tee /tmp/molecule-dev-env-rocky-coderabbit-cli.out
```

```bash
git diff --check 2>&1 | tee /tmp/diff-check-dev-env-rocky-coderabbit-cli.out
```

After each major milestone, run:

```bash
coderabbit review --agent 2>&1 | tee /tmp/coderabbit-review-dev-env-rocky-coderabbit-cli.out
```

The final completion audit must map every requirement from the user objective
to actual artefacts and command evidence.

## Outcomes & Retrospective

The implementation installs and authenticates CodeRabbit CLI through a
dedicated role, adds deterministic Molecule coverage, stores both host API keys
as inline Ansible Vault values, updates user and developer documentation, and
wires the new role into the normal user-environment playbook and Molecule gate.

The only incomplete external signal is CodeRabbit's hosted review result: the
CLI reached the service with `--api-key`, but the service rejected the review
because the account has no usage credits. That is an account-state blocker, not
a local implementation failure.
