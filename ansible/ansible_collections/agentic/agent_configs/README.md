# agentic.agent_configs

An Ansible collection for managing filesystem-backed configuration used by
Claude Code, Codex CLI, and Factory Droid.

The collection currently includes fifteen modules:

- `json_file`
- `toml_file`
- `claude_code_mcp`
- `claude_code_hook`
- `claude_code_skill`
- `claude_code_command`
- `codex_cli_mcp`
- `codex_cli_hook`
- `codex_cli_skill`
- `codex_cli_subagent`
- `factory_droid_mcp`
- `factory_droid_hook`
- `factory_droid_skill`
- `factory_droid_droid`
- `factory_droid_model`

## Design notes

These modules edit the underlying JSON, TOML, and Markdown files directly
rather than shelling out to the agent CLIs. That keeps them idempotent and easy
to use in check mode.

Hook modules require an `agent_executable` parameter, matching the assumption
you asked for. The current implementation records and optionally validates that
path, but it does not invoke the CLI.

Codex modules read and rewrite TOML on Rocky 10+ hosts with Python 3.12+. The
generic `toml_file` module also requires `tomlkit` so it can update TOML values
without raw text blocks.

`claude_code_mcp` currently manages user and project scopes. It does not
attempt to manipulate Claude's local per-project MCP storage inside
`~/.claude.json`.

## Example

```yaml
---
- hosts: localhost
  connection: local
  gather_facts: false

  collections:
    - agentic.agent_configs

  tasks:
    - name: Configure a Claude project MCP server
      claude_code_mcp:
        name: repo-tools
        scope: project
        project_dir: /srv/my-repo
        transport: stdio
        command: /usr/local/bin/repo-tools-mcp
        args:
          - --stdio

    - name: Add a Codex project hook
      codex_cli_hook:
        agent_executable: /home/payton/.local/bin/codex
        scope: project
        project_dir: /srv/my-repo
        event: PostToolUse
        matcher: Bash
        command: /srv/my-repo/.codex/hooks/post-bash.sh
        status_message: Running repository checks

    - name: Create a Factory Droid reviewer droid
      factory_droid_droid:
        name: Reviewer
        scope: project
        project_dir: /srv/my-repo
        description: Review changes and call out correctness risks.
        model: inherit
        reasoning_effort: high
        tools:
          - Read
          - Edit
          - Execute
        body: |
          Review the supplied changes and highlight concrete defects.

    - name: Configure a Factory Droid custom model
      factory_droid_model:
        model: deepseek-v4-pro
        display_name: DeepSeek V4 Pro
        provider: anthropic
        base_url: https://api.deepseek.com/anthropic
        api_key: "{{ deepseek_api_key }}"
      no_log: true
```
