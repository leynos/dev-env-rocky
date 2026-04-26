"""Tests for sourceable shell bootstrap helper functions."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_COMMON = REPO_ROOT / "bootstrap-common"
INSTALL_SUB_AGENTS = REPO_ROOT / "install-sub-agents"


def run_bash(tmp_path: Path, script: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["PATH"] = "/usr/bin:/bin"
    return subprocess.run(
        ["bash", "-c", script],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_append_block_if_missing_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / ".bashrc"

    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {BOOTSTRAP_COMMON}
        append_block_if_missing {target} test-marker 'export EXAMPLE=1'
        append_block_if_missing {target} test-marker 'export EXAMPLE=1'
        """,
    )

    assert result.returncode == 0, result.stderr
    content = target.read_text()
    assert content.count("### BEGIN test-marker") == 1
    assert content.count("### END test-marker") == 1
    assert content.count("export EXAMPLE=1") == 1


def test_ensure_profile_path_is_idempotent(tmp_path: Path) -> None:
    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {BOOTSTRAP_COMMON}
        ensure_profile_path "$HOME/.local/bin"
        ensure_profile_path "$HOME/.local/bin"
        """,
    )

    assert result.returncode == 0, result.stderr
    bashrc = tmp_path / ".bashrc"
    line = f'export PATH="{tmp_path}/.local/bin:${{PATH}}"'
    assert bashrc.read_text().count(line) == 1


def test_ensure_profile_sources_bashrc_is_idempotent(tmp_path: Path) -> None:
    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {BOOTSTRAP_COMMON}
        ensure_profile_sources_bashrc
        ensure_profile_sources_bashrc
        """,
    )

    assert result.returncode == 0, result.stderr
    profile = tmp_path / ".profile"
    line = '[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"'
    assert profile.read_text().count(line) == 1


def test_ensure_runtime_path_updates_current_process_path(tmp_path: Path) -> None:
    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {BOOTSTRAP_COMMON}
        ensure_runtime_path "$HOME/.cargo/bin"
        printf '%s\\n' "$PATH"
        """,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f"{tmp_path}/.cargo/bin:/usr/bin:/bin"]


def test_replace_managed_block_replaces_existing_block(tmp_path: Path) -> None:
    target = tmp_path / "agents.md"
    target.write_text(
        "before\n"
        "### BEGIN sub-agents\n"
        "old content\n"
        "### END sub-agents\n"
        "after\n"
    )

    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {INSTALL_SUB_AGENTS}
        replace_managed_block {target} sub-agents 'new content'
        """,
    )

    assert result.returncode == 0, result.stderr
    assert target.read_text() == (
        "before\n"
        "### BEGIN sub-agents\n"
        "new content\n"
        "### END sub-agents\n"
        "after\n"
    )
    content = target.read_text()
    assert content.count("### BEGIN sub-agents") == 1
    assert content.count("### END sub-agents") == 1


def test_replace_managed_block_rejects_unbalanced_sentinels(tmp_path: Path) -> None:
    target = tmp_path / "agents.md"
    original = "before\n### BEGIN sub-agents\nold content\n"
    target.write_text(original)

    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {INSTALL_SUB_AGENTS}
        replace_managed_block {target} sub-agents 'new content'
        """,
    )

    assert result.returncode != 0
    assert "replace_managed_block: unbalanced sentinels" in result.stderr
    assert "sub-agents" in result.stderr
    assert str(target) in result.stderr
    assert target.read_text() == original
