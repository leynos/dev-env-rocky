"""Snapshot tests for generated DeepSeek-TUI configuration artefacts."""

import json
from pathlib import Path

from ansible_collections.agentic.agent_configs.plugins.modules import (
    deepseek_tui_hook,
    deepseek_tui_mcp,
    deepseek_tui_skill,
)
from ansible_module_runner import run_module


def test_deepseek_tui_generated_configuration_matches_snapshot(
    tmp_path: Path,
    snapshot,
) -> None:
    """Capture the generated DeepSeek-TUI MCP, hook, and skill files."""
    deepseek_home = tmp_path / ".deepseek"
    deepseek_home.mkdir()

    run_module(
        deepseek_tui_mcp,
        {
            "path": str(deepseek_home / "mcp.json"),
            "name": "repo-tools",
            "transport": "stdio",
            "command": "repo-tools-mcp",
            "args": ["--stdio"],
            "env": {"LOG_LEVEL": "info"},
            "required": True,
        },
    )
    run_module(
        deepseek_tui_hook,
        {
            "path": str(deepseek_home / "config.toml"),
            "event": "session_start",
            "name": "announce",
            "command": "printf 'ready\\n'",
            "timeout_secs": 10,
            "enabled": True,
        },
    )
    run_module(
        deepseek_tui_skill,
        {
            "path": str(deepseek_home / "skills" / "repo-reviewer"),
            "name": "Repo reviewer",
            "description": "Review repository changes.",
            "body": "Read AGENTS.md before reviewing.",
            "extra_files": {"references/checklist.md": "Check tests and docs.\n"},
        },
    )

    generated = {
        "config.toml": (deepseek_home / "config.toml").read_text(),
        "mcp.json": json.dumps(
            json.loads((deepseek_home / "mcp.json").read_text()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "skills/repo-reviewer/SKILL.md": (
            deepseek_home / "skills" / "repo-reviewer" / "SKILL.md"
        ).read_text(),
        "skills/repo-reviewer/references/checklist.md": (
            deepseek_home / "skills" / "repo-reviewer" / "references" / "checklist.md"
        ).read_text(),
    }

    assert generated == snapshot
