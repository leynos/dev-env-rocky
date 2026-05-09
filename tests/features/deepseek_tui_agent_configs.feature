Feature: DeepSeek-TUI agent configuration modules
  Operators can provision DeepSeek-TUI configuration through reusable Ansible
  modules without replacing unrelated user-managed settings.

  Scenario: Provision DeepSeek-TUI MCP, hook, and skill files
    Given an empty DeepSeek-TUI home directory
    When the DeepSeek-TUI modules provision a repository toolset
    Then the MCP server is written to the DeepSeek servers file
    And the shell environment hook is written to config TOML
    And the skill bundle is written to the DeepSeek skills directory
