"""Snapshot tests for generated DeepSeek-TUI configuration artefacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest  # ty: ignore[unresolved-import]
from ansible_collections.agentic.agent_configs.plugins.modules import (
    deepseek_tui_hook,
    deepseek_tui_mcp,
    deepseek_tui_skill,
)
from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    AnsibleExitJson,
    set_module_args,
)


def _run_module(module: Any, args: dict[str, Any]) -> dict[str, Any]:
    """Run an Ansible module in-process and return its exit payload."""
    set_module_args(args)
    with pytest.raises(AnsibleExitJson) as exc:
        module.main()
    return exc.value.args[0]


def test_deepseek_tui_generated_configuration_matches_snapshot(
    tmp_path: Path,
    snapshot,
) -> None:
    """Capture the generated DeepSeek-TUI MCP, hook, and skill files."""
    deepseek_home = tmp_path / ".deepseek"
    deepseek_home.mkdir()

    _run_module(
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
    _run_module(
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
    _run_module(
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
