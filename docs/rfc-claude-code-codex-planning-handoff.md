# RFC: Claude Code to Codex Planning Handoff

## Summary

Claude Code can plausibly start Codex for planning in two supported ways: as a
stdio Model Context Protocol (MCP) server, or as a background command launched
from a hook or command wrapper. The repository already installs `context_pack`,
registers `context_pack` as an MCP server for Claude Code and Codex, and
defines a Codex `wyvern` subagent. The missing work is orchestration: deciding
who owns the planning request, how the `context_pack` evidence bundle is
created, and how Claude receives the final planning result.

This RFC proposes three implementation paths:

- Register Codex as a Claude Code MCP server and let Claude call Codex through
  MCP.
- Add a Claude-launched background wrapper around `codex exec`.
- Add a local orchestration MCP server that packages context, launches Codex,
  tracks status, and returns artefacts.

The recommended path is to prototype Codex-as-MCP first, then use the
orchestration MCP server if Codex's MCP surface does not expose a reliable
"start planning task" operation.

## Goals

- Let Claude Code hand a planning request to Codex without losing repository
  context.
- Let Codex use a `wyvern` reconnaissance team for planning research.
- Use `context_pack` as the evidence bundle between workers and the lead agent.
- Keep secrets, filesystem permissions, and long-running task state explicit.
- Preserve idempotent Ansible configuration through `agentic.agent_configs`.

## Non-goals

- Replacing Claude Code's native agent teams.
- Implementing a production daemon before proving the Codex handoff contract.
- Assuming Claude Code can call Codex's internal subagent API directly.
- Granting broad sandbox bypasses as the default planning path.

## Current State

The local role already contains most of the substrate:

- `agent_tools` installs `context_pack` from the upstream installer and expects
  `~/.local/bin/context_pack` to exist afterwards.[^local-context-pack-install]
- The same role registers a `context_pack` stdio MCP server for:
  - Codex.[^local-codex-context-pack]
  - Claude Code and Cursor CLI.[^local-claude-context-pack]
  - Factory Droid.[^local-factory-context-pack]
- The registered context-pack environment uses a shared storage root under
  `~/.local/state/context-pack` and sets `CONTEXT_PACK_SOURCE_ROOT` to
  `__SESSION_CWD__`.[^local-codex-context-pack]
- The role already defines a Codex `wyvern` subagent for fast, read-only
  reconnaissance.[^local-wyvern]
- The `codex_cli_subagent` module supports an `mcp_servers` list in generated
  Codex subagent TOML files, although the current role does not pass that field
  to `wyvern`.[^local-subagent-mcp]
- The roadmap already identifies duplicated MCP registration as work to extract
  into a shared MCP definition contract.[^local-roadmap-mcp]

External documentation confirms the integration points:

- Claude Code supports stdio MCP servers and stores MCP configuration at local,
  project, user, or managed scopes.[^claude-mcp]
- Claude Code hooks can run shell commands, HTTP calls, prompts, or agents at
  lifecycle events. Command hooks can run asynchronously.[^claude-hooks]
- Claude Code agent teams are experimental, disabled by default, and require
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Teammates load the same project
  context as a regular Claude Code session, including MCP servers and skills.
  [^claude-agent-teams]
- Codex supports `codex mcp-server`, which starts Codex as a stdio MCP server
  for other tools to connect to.[^codex-cli-reference]
- Codex supports MCP server configuration in `~/.codex/config.toml`, including
  stdio commands and environment variables.[^codex-mcp]
- Codex subagents are intended for parallel specialised work while the main
  agent remains focused on decisions and final synthesis.[^codex-subagents]
- The context-pack MCP package is designed for high-signal multi-agent handoff:
  agents create packs, add file anchors and comments, then return a `pack_id`
  plus a short summary to the orchestrator.[^context-pack]

Local command checks add two caveats:

- The installed Codex command is `codex-cli 0.129.0`, and
  `codex mcp-server --help` confirms the stdio MCP entrypoint.
- The local `claude` shim currently fails before printing help because its
  native binary has not been installed. This blocks an end-to-end local smoke
  test until the Claude Code install is repaired.

## Feasibility Answer

The broad workflow is possible. Claude Code can start a stdio MCP server, Codex
can run as a stdio MCP server, both clients can use `context_pack`, and Codex
can run subagents. What is not yet proven is the strongest version of the
workflow: Claude invoking Codex over MCP and causing Codex to spawn a `wyvern`
team for a planning task without any wrapper.

That uncertainty leads to three viable proposals.

## Proposal A: Codex as a Claude Code MCP Server

Register Codex itself as a Claude Code MCP server:

```json
{
  "mcpServers": {
    "codex": {
      "type": "stdio",
      "command": "codex",
      "args": ["mcp-server"]
    }
  }
}
```

Claude would call the Codex MCP server with a planning prompt. Codex would run
inside its own session, use the existing `context_pack` MCP server, spawn
`wyvern` subagents where appropriate, and return the planning result.

### Proposal A Required Changes

- Add a `codex` MCP entry to the Claude Code MCP registration loop.
- Decide whether the entry is user-scoped, project-scoped, or managed.
- Add `mcp_servers: ["context_pack"]` to the Codex `wyvern` subagent entry so
  reconnaissance workers can create and read context packs directly.
- Add a focused regression test that renders the Claude Code MCP entry for
  `codex` with `command: codex` and `args: ["mcp-server"]`.
- Add a smoke test that starts `codex mcp-server` and performs the minimum MCP
  handshake, once an MCP test harness is available.

### Proposal A Decisions

- Does `codex mcp-server` expose a tool that starts a planning task and returns
  durable output, or does it only expose lower-level Codex operations?
- Should Claude receive the full plan directly, or only a path plus pack ID?
- Should this be enabled by default, or gated behind a variable such as
  `dev_env_enable_claude_codex_mcp`?
- Which Codex sandbox and approval settings should apply when Claude starts the
  server?

### Proposal A Benefits

- Uses published MCP surfaces from both tools.
- Keeps lifecycle simple: Claude starts Codex on demand as a stdio server.
- Avoids inventing a daemon or task store before proving the workflow.

### Proposal A Risks

- If Codex MCP does not expose a suitable "run this task" operation, this path
  will still need a wrapper.
- Long-running plans may exceed normal MCP request expectations.
- Error reporting depends on the current Codex MCP tool contract.

## Proposal B: Claude-Launched Background Codex Task

Add a small wrapper command that Claude can run from a custom command, skill,
or asynchronous hook. The wrapper would create a planning request file, invoke
`codex exec`, and write outputs to a predictable state directory.

Example flow:

1. Claude writes a request manifest with the user request, repository path,
   branch, desired worker count, and context-pack TTL.
2. The wrapper creates or updates a context pack with the relevant requirements
   and repository anchors.
3. The wrapper runs `codex exec --jsonl` with a prompt instructing Codex to
   spawn a `wyvern` team and return a plan plus pack ID.
4. Claude reads the final Markdown plan and any JSONL event log from the state
   directory.

### Proposal B Required Changes

- Add a wrapper script under the agent helper scripts or this role's managed
  files.
- Install a Claude Code command or hook that can call the wrapper.
- Add a state layout, for example:
  `~/.local/state/claude-codex-planning/{task_id}/`.
- Add log retention, lock files, and cancellation semantics.
- Configure Codex `wyvern` with access to `context_pack`.

### Proposal B Decisions

- Should the task start only when the user invokes a command, or from a hook?
- Should background tasks be allowed during Stop hooks, or only explicit user
  commands?
- What concurrency limit prevents multiple expensive Codex plans from running
  at once?
- How does Claude discover task completion: polling, notification, or reading
  a known result path?

### Proposal B Benefits

- Does not depend on Codex MCP exposing a high-level planning tool.
- Fits Claude Code's documented asynchronous command hook capability.
- Produces durable logs and artefacts that can be inspected after completion.

### Proposal B Risks

- Hooks run with the user's full permissions, so the wrapper needs strict input
  validation, absolute paths, quoting, and a narrow command surface.
- Background work is easier to orphan than stdio MCP work.
- Claude would need a separate status command to inspect running tasks.

## Proposal C: Local Planning Orchestrator MCP

Add a small local MCP server, for example `claude-codex-planner-mcp`, and
expose it to Claude Code. Claude would call tools such as `planning.start`,
`planning.status`, `planning.result`, and `planning.cancel`. The MCP server
would own context-pack creation, Codex invocation, output collection, and
status.

Internally the server could start with `codex exec`. If Proposal A later proves
that Codex MCP can start a task directly, the server could switch from process
execution to Codex MCP calls without changing Claude's interface.

### Proposal C Required Changes

- Build a small MCP server with a deliberately narrow tool contract.
- Store request manifests, logs, context-pack IDs, and results under
  `~/.local/state/claude-codex-planning/`.
- Register the orchestrator MCP in Claude Code.
- Keep `context_pack` registered in both Claude and Codex.
- Add unit tests for manifest validation, path policy, task status transitions,
  and result rendering.

### Proposal C Decisions

- Is the orchestrator implemented in Python, Rust, or shell plus a small MCP
  adapter?
- Does it launch Codex via `codex exec`, `codex mcp-server`, or a selectable
  backend?
- What task statuses are stable API: `queued`, `running`, `succeeded`,
  `failed`, `cancelled`, and `expired`?
- Which artefacts are returned inline, and which are returned as paths or
  context-pack IDs?
- What cleanup policy keeps state bounded without deleting useful evidence?

### Proposal C Benefits

- Gives Claude a stable API regardless of Codex CLI details.
- Makes long-running planning observable and cancellable.
- Keeps shell execution and path validation out of Claude prompts.

### Proposal C Risks

- Adds a new maintained component.
- Requires MCP server tests and operational docs.
- Duplicates some process supervision that Claude Code agent teams already
  provide for Claude-native teammates.

## Proposal D: Use Claude Code Agent Teams Instead

Claude Code can already run experimental agent teams. Teammates have their own
context windows, can communicate through team resources, and load the same MCP
servers as regular sessions. Claude can also use subagent definitions as
teammate role templates.

This is a good fallback if the goal is "Claude-led multi-agent planning with
context-pack evidence" rather than "Codex-led planning with `wyvern` workers".
It does not satisfy the Codex-specific part of the request, because Claude
teammates are Claude Code sessions rather than Codex subagents.

### Proposal D Required Changes

- Enable `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in Claude Code settings.
- Ensure the Claude Code MCP registration includes `context_pack`.
- Add a Claude Code subagent or teammate role equivalent to `wyvern`.
- Document team size, cleanup, and cost guidance.

### Proposal D Decisions

- Is Codex specifically required for planning, or is Claude-native planning
  acceptable?
- Should team usage remain manual because agent teams are experimental?
- How will team cleanup and orphaned sessions be monitored?

## Shared Implementation Requirements

All proposals need the same groundwork:

- Repair the local Claude Code installation before any end-to-end validation.
- Centralise repeated MCP definitions as already planned in roadmap step 2.2.
- Configure Codex `wyvern` with `context_pack` MCP access.
- Define a context-pack contract:
  - pack owner and TTL;
  - required sections;
  - expected repository anchors;
  - maximum rendered size;
  - rule that chat returns `pack_id` plus summary, not all evidence.
- Define a task manifest contract containing:
  - repository path and branch;
  - user request;
  - planning mode;
  - allowed tools and MCP servers;
  - sandbox and approval policy;
  - output paths.
- Add explicit toggles so the integration is not enabled accidentally on hosts
  that only need Claude Code or only need Codex.
- Treat all command-launching paths as security-sensitive. Claude hook
  documentation explicitly warns that hooks run with user permissions, so
  wrappers must validate paths and quote shell inputs.

## Recommendation

Prototype in this order:

1. Repair the local Claude Code install and confirm `claude --version`.
2. Register `codex` as a Claude Code stdio MCP server with
   `command: codex` and `args: ["mcp-server"]`.
3. Confirm whether Claude can start a planning request through Codex MCP and
   receive a useful result.
4. In parallel, add `mcp_servers: ["context_pack"]` to the Codex `wyvern`
   subagent config and validate the rendered TOML.
5. If Codex MCP lacks a high-level planning tool, implement Proposal C rather
   than Proposal B. The orchestrator MCP gives Claude a cleaner API and avoids
   hiding long-running task state inside hooks.

Proposal B remains useful as a low-cost experiment or emergency fallback, but
it should not be the final design if planning tasks need status, cancellation,
and durable evidence.

## Open Questions

- What exact tool contract does `codex mcp-server` expose in Codex CLI
  `0.129.0`?
- Should `wyvern` always receive `context_pack`, or should the role make that
  opt-in per subagent?
- Should context packs be shared across Claude and Codex sessions by default,
  or should each planning task get an isolated pack namespace?
- Where should planning results live: under `~/.local/state`, inside the
  repository, or only inside context-pack?
- Should Claude Code be allowed to start background Codex work from hooks, or
  only from explicit commands?
- What is the maximum acceptable cost and runtime for a planning team?

## References

[^local-context-pack-install]: `ansible/roles/agent_tools/tasks/main.yml`,
    lines 417-422.
[^local-codex-context-pack]: `ansible/roles/agent_tools/tasks/main.yml`, lines
    444-464.
[^local-claude-context-pack]: `ansible/roles/agent_tools/tasks/main.yml`, lines
    655-677.
[^local-factory-context-pack]: `ansible/roles/agent_tools/tasks/main.yml`,
    lines 912-933.
[^local-wyvern]: `ansible/roles/agent_tools/tasks/main.yml`, lines 505-537.
[^local-subagent-mcp]:
    `ansible/ansible_collections/agentic/agent_configs/plugins/modules/codex_cli_subagent.py`,
    lines 109-113 and 181-190.
[^local-roadmap-mcp]: `docs/roadmap.md`, lines 126-153.
[^claude-mcp]: Claude Code documentation, "Model Context Protocol (MCP)",
    <https://code.claude.com/docs/en/mcp>.
[^claude-hooks]: Claude Code documentation, "Hooks",
    <https://code.claude.com/docs/en/hooks>.
[^claude-agent-teams]: Claude Code documentation, "Orchestrate teams of Claude
    Code sessions", <https://code.claude.com/docs/en/agent-teams>.
[^codex-cli-reference]: OpenAI Codex CLI reference,
    <https://developers.openai.com/codex/cli/reference>.
[^codex-mcp]: OpenAI Codex MCP documentation,
    <https://developers.openai.com/codex/mcp>.
[^codex-subagents]: OpenAI Codex subagent documentation,
    <https://developers.openai.com/codex/concepts/subagents>.
[^context-pack]: LobeHub MCP listing for `AmirTlinov/context_pack`,
    <https://lobehub.com/bg/mcp/amirtlinov-context_pack>.
