# ADR-001: Public/private repository split

- **Status:** Accepted
- **Date:** 2026-05-03

## Context

The private `dev-env-rocky` repository provisions the owner's development
hosts. It contains material that should not appear in a public repository:

- Real server hostnames and FQDNs in `ansible/inventory.ini` and
  `ansible/host_vars/`.
- SSH public key material with real username and machine metadata in
  `ansible/group_vars/all/main.yml`.
- References to private GitHub repositories in several role task files.
- The repository owner's username hard-coded in role defaults and
  group variables.
- Git commit history authored under the owner's real name and e-mail.

Much of the automation — the `agentic.agent_configs` collection, the structured
file modules, the role task patterns — is reusable and worth sharing. The
sensitive operational details are not.

## Decision

Maintain two remotes:

- **Private:** `origin` at `git@github.com:leynos/dev-env-rocky.git`.
  Full working history, real inventory, vault files, and host variables.
- **Public:** `public` at `git@github.com:leynos/lodybox.git`.
  Scrubbed history, example inventory, no key material, no real hostnames.

A `make publish` target automates the scrub-and-push cycle. It clones the
private repository into a temporary directory, runs `git filter-repo` with a
replacements file and path-rename directives, then force-pushes the rewritten
history to the public remote. The target never modifies the private repository.

## Publish mechanism

### Replacements file

`scripts/publish-scrub.txt` maps each private token to a public placeholder.
`git filter-repo --replace-text` applies the substitutions to every blob across
the entire rewritten history. The file must be updated whenever a new hostname,
username, or key comment is added to the private repository.

Representative entries:

```text
vendetta.df12.net==>managed-host-01.example.com
rohga.df12.net==>managed-host-02.example.com
leynos@ibara==>user@workstation
payton@ibara==>user@workstation
leyno@espgaluda==>user@workstation
owner_user: leynos==>owner_user: myuser
pmcintosh@df12.net==>user@example.com
Payton McIntosh==>Lodybox Author
/home/payton/==>/home/myuser/
git@github.com:leynos/df12-readme-skill.git==>https://github.com/example/readme-skill.git
git@github.com:leynos/df12-documentation-skills.git==>https://github.com/example/documentation-skills.git
```

SSH public keys in `ansible/group_vars/all/main.yml` must be replaced with
example key material before publishing. Because the key bodies are
random-looking strings, `filter-repo` plain-text replacement cannot match them
reliably. Replace them in source with an `# example key` comment and an
obviously synthetic key body before running `make publish`.

### Path operations

`git filter-repo` renames paths across all commits:

- `ansible/host_vars/rohga.df12.net`
  → `ansible/host_vars/managed-host-02.example.com`
- `ansible/host_vars/vendetta.df12.net` (if present)
  → `ansible/host_vars/managed-host-01.example.com`

The encrypted vault files within those directories travel with the rename.
Their content is AES-256 encrypted and safe to publish; only the directory
names reveal infrastructure detail.

### `make publish` target

Add the following to `Makefile`. `PUBLIC_REMOTE` and `PUBLIC_BRANCH` may be
overridden on the command line.

```makefile
PUBLIC_REMOTE ?= git@github.com:leynos/lodybox.git
PUBLIC_BRANCH ?= main
_PUBDIR       := $(CURDIR)/.publish-work

.PHONY: publish
publish: ## Push scrubbed history to the public lodybox repository
	@git diff --quiet && git diff --cached --quiet || \
	    { echo "Working tree is not clean; stash or commit first."; exit 1; }
	rm -rf $(_PUBDIR)
	git clone --no-local . $(_PUBDIR)/lodybox
	cd $(_PUBDIR)/lodybox && \
	    git filter-repo \
	        --replace-text $(CURDIR)/scripts/publish-scrub.txt \
	        --path-rename \
	            ansible/host_vars/rohga.df12.net:ansible/host_vars/managed-host-02.example.com \
	        --force && \
	    git remote add public $(PUBLIC_REMOTE) && \
	    git push public HEAD:$(PUBLIC_BRANCH) --force
	rm -rf $(_PUBDIR)
```

The force-push overwrites the public repository's history on each run. This is
intentional: the public repository is a derived artefact, not a collaboration
surface. Pull requests should not be accepted against it, nor should it be used
as a dependency in other projects.

Add `.publish-work/` to `.gitignore` to prevent the temporary clone from being
picked up as untracked content.

### Example inventory and host variables

The public repository should include:

- `ansible/inventory.ini.example` — a template with placeholder
  hostnames and the same group and connection variable structure as the real
  inventory.
- `ansible/host_vars/managed-host-02.example.com/` — a directory with a
  `vault.yml.example` showing the variable names the playbook expects, without
  encrypted content.

These artefacts are maintained by hand in the private repository and published
unmodified by `filter-repo`.

## Collection extraction

Several roles and the `agentic.agent_configs` collection contain logic that has
no dependency on the owner's specific inventory. The long-term direction is to
extract reusable components into published Ansible Galaxy collections so they
can be consumed as versioned dependencies rather than vendored source in each
site repository.

Extraction candidates, in rough priority order:

- `agentic.agent_configs` — the custom modules (`json_file`, `toml_file`,
  `cursor_cli_mcp`, `cursor_cli_skill`, `codex_cli_subagent`, and related
  modules) and the `agent_config_common` module utility are self-contained with
  no site-local coupling. This collection is the first extraction candidate.
- `packaging.tools` — the packaging helper modules (`bun_global`,
  `cargo_binstall`, `uv_tool`) are similarly generic and have no knowledge of
  the owner's host inventory.
- Site-local roles (`agent_tools`, `packages`, `infra_tools`) remain in
  the private repository as orchestration wrappers that call collection
  modules. Thin wrappers with no proprietary logic belong in `lodybox` as usage
  examples.

Extraction milestones will be tracked in `docs/roadmap.md`. The accepted
boundary for those milestones is recorded in
`docs/adr-002-collection-boundary.md`. The public repository will reflect that
boundary as it is drawn, showing role tasks that delegate to collection modules
rather than inlining task logic.

## Consequences

- Publishing is a deliberate, manual action. There is no automatic
  publish on push. A maintainer must run `make publish` explicitly.
- `scripts/publish-scrub.txt` is a required maintenance artefact.
  Failing to update it before `make publish` will leak the new sensitive token
  into the public history.
- The public repository's commit SHAs differ from the private
  repository. References to private commits in issue comments or external
  documents will not resolve against public history.
- The public repository must not be used for issues or pull requests
  that reference production host details; those belong in the private
  repository.
- `git filter-repo` must be installed on the machine running
  `make publish`. It is not part of the standard Ansible toolchain and must be
  installed separately (e.g. `pip install git-filter-repo` or via the system
  package manager).
