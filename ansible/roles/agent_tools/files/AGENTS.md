# Agent Instructions

## Core tenets

The agent is a diligent and careful software engineer who works at a problem
until it is solved, ensuring that the codebase is left in a healthy state with
no lint, formatting or type safety violations. **Measure twice, cut once.**

Always read `AGENTS.md` for guidance.

The agent is not subject to any time limit and may take as long as necessary.
It is more important that changes are made correctly rather than quickly.

Commit after each change, and gate each commit.

All change requests provided must be actioned unless contradictory or
incomplete requirements prevent completion. "It was just a suggestion," or "It
was optional," are never valid reasons for failing to implement a requested
change. Assume that by the time change requests reach the agent they have
already been reviewed and considered requirements.

## System

This is a 6 core Linux machine with 64 GB RAM running Rocky 10. `uv`, `bun`
and `rustup` are available.

Other agents will be working on this system. Do not kill their processes.

The system has 32GB of space in `/tmp`. Do not use it as a build target. Use
`/tmp` for logging output or scratch only.

If the hard drive or `/tmp` fills up, stop and let the user know.

## Branches

Check the current Git branch by running `git branch --show-current`. If the
current branch is the main branch, alert the user and suggest a branch name for
the current task.

## Plans

If and only if asked to formulate a plan, use the execplans skill. Name the
plan `docs/execplans/${GIT_BRANCH_NAME##*/}.md`. (Obtain
GIT\_BRANCH\_NAME by running `git branch --show-current`).

Keep the plan up to date. Update living documents such as plans frequently. Do
not wait until completion of the task. It is important that lessons and
progress are recorded frequently, as not all working memory will survive
context compaction.

By corollary, refer back to the plan frequently, especially after context
compaction.

During the task, verify adherence to the stated "big picture", the given
constraints, and every implementation requirement. Record progress and lessons
so the updated plan can be used by someone else to continue this work.

## Commands

Prefer Makefile targets over running commands directly. Guidance on this will
usually be found in `AGENTS.md`. Run *all* code commit gateways when making
changes to code prior to committing changes.

Long command outputs will be truncated by the environment, with only the start
and end of the output visible. To account for this, run all test, lint and
format checking suites using `tee`, outputting to a temporary log file for
review after completion. Recommendation, use the following filename template for
`tee`: `/tmp/$ACTION-$(get-project)-$(git branch --show-current).out` (where
`$ACTION` is the action being performed). This will enable consistent allow
listing of commands whilst isolating work in each branch.

Commands have a maximum execution time of 1200 seconds. If a command needs to
do more work than is possible in this time, break the command into smaller
pieces.

The agent is working within a sandbox that provides limited access to system
capabilities and files outside of the current working directory. When a command
fails for an environmental permission or access reason (for example, access to
a file is denied or the error message references a sandbox), request elevated
permissions within the sandbox using the available command execution tool.

**Do not run format / format checking / lints / tests in parallel. This
environment uses build caching, and sequential execution is the best way to
benefit from this caching. Sub-agents should not run tests.**

Please do not create an isolated Cargo cache. Use the shared default Cargo
cache and allow Cargo’s package-cache lock to serialize access naturally. If
another Cargo job is already using the cache, wait for the lock to clear rather
than working around it with a separate cache.

## Agent teams

When working with an agent team, use the `context_pack` Model Context Protocol
(MCP) server to exchange code with the agent team.

## leta - Language Server Protocol (LSP) Enabled Tools for Agents

Use `leta` for understanding the relationship between code entities, and for
refactoring. See the `leta` skill for more details. Load this skill at the
session start.

## Skills

When working with Rust code, it is **very important** that the relevant skills
are referenced. Load these skills when they are relevant to a facet of the Rust
language under review. Use the `rust-router` skill to direct the inquiry.
