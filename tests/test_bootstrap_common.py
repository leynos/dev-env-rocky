"""Tests for sourceable shell bootstrap helper functions."""

from __future__ import annotations

import os
import shlex
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
    bootstrap_common = shlex.quote(str(BOOTSTRAP_COMMON))
    target_arg = shlex.quote(str(target))

    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {bootstrap_common}
        append_block_if_missing {target_arg} test-marker 'export EXAMPLE=1'
        append_block_if_missing {target_arg} test-marker 'export EXAMPLE=1'
        """,
    )

    assert result.returncode == 0, f"append_block_if_missing failed: {result.stderr}"
    content = target.read_text()
    assert content.count("### BEGIN test-marker") == 1, f"expected one BEGIN sentinel, got {content!r}"
    assert content.count("### END test-marker") == 1, f"expected one END sentinel, got {content!r}"
    assert content.count("export EXAMPLE=1") == 1, f"expected one managed block body, got {content!r}"


def test_ensure_profile_path_is_idempotent(tmp_path: Path) -> None:
    bootstrap_common = shlex.quote(str(BOOTSTRAP_COMMON))

    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {bootstrap_common}
        ensure_profile_path "$HOME/.local/bin"
        ensure_profile_path "$HOME/.local/bin"
        """,
    )

    assert result.returncode == 0, f"ensure_profile_path failed: {result.stderr}"
    bashrc = tmp_path / ".bashrc"
    line = f'export PATH="{tmp_path}/.local/bin:${{PATH}}"'
    content = bashrc.read_text()
    assert content.count(line) == 1, f"expected one PATH line {line!r} in {bashrc}, got {content!r}"


def test_ensure_profile_sources_bashrc_is_idempotent(tmp_path: Path) -> None:
    bootstrap_common = shlex.quote(str(BOOTSTRAP_COMMON))

    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {bootstrap_common}
        ensure_profile_sources_bashrc
        ensure_profile_sources_bashrc
        """,
    )

    assert result.returncode == 0, f"ensure_profile_sources_bashrc failed: {result.stderr}"
    profile = tmp_path / ".profile"
    line = '[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"'
    content = profile.read_text()
    assert content.count(line) == 1, f"expected one source line {line!r} in {profile}, got {content!r}"


def test_ensure_runtime_path_updates_current_process_path(tmp_path: Path) -> None:
    bootstrap_common = shlex.quote(str(BOOTSTRAP_COMMON))

    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {bootstrap_common}
        ensure_runtime_path "$HOME/.cargo/bin"
        printf '%s\\n' "$PATH"
        """,
    )

    assert result.returncode == 0, f"ensure_runtime_path failed: {result.stderr}"
    expected_path = [f"{tmp_path}/.cargo/bin:/usr/bin:/bin"]
    assert result.stdout.splitlines() == expected_path, (
        f"expected runtime PATH output {expected_path!r}, got {result.stdout!r}"
    )


def test_replace_managed_block_replaces_existing_block(tmp_path: Path) -> None:
    target = tmp_path / "agents.md"
    install_sub_agents = shlex.quote(str(INSTALL_SUB_AGENTS))
    target_arg = shlex.quote(str(target))
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
        source {install_sub_agents}
        replace_managed_block {target_arg} sub-agents 'new content'
        """,
    )

    assert result.returncode == 0, f"replace_managed_block failed: {result.stderr}"
    expected = (
        "before\n"
        "### BEGIN sub-agents\n"
        "new content\n"
        "### END sub-agents\n"
        "after\n"
    )
    assert target.read_text() == expected, f"expected replaced content {expected!r}, got {target.read_text()!r}"
    content = target.read_text()
    assert content.count("### BEGIN sub-agents") == 1, f"expected one BEGIN sentinel, got {content!r}"
    assert content.count("### END sub-agents") == 1, f"expected one END sentinel, got {content!r}"


def test_replace_managed_block_rejects_unbalanced_sentinels(tmp_path: Path) -> None:
    target = tmp_path / "agents.md"
    install_sub_agents = shlex.quote(str(INSTALL_SUB_AGENTS))
    target_arg = shlex.quote(str(target))
    original = "before\n### BEGIN sub-agents\nold content\n"
    target.write_text(original)

    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        source {install_sub_agents}
        replace_managed_block {target_arg} sub-agents 'new content'
        """,
    )

    assert result.returncode != 0, "expected replace_managed_block to reject unbalanced sentinels"
    assert "replace_managed_block: unbalanced sentinels" in result.stderr, (
        f"expected unbalanced sentinel diagnostic, got {result.stderr!r}"
    )
    assert "sub-agents" in result.stderr, f"expected marker in stderr, got {result.stderr!r}"
    assert str(target) in result.stderr, f"expected target path in stderr, got {result.stderr!r}"
    assert target.read_text() == original, (
        f"expected unbalanced failure to preserve original {original!r}, got {target.read_text()!r}"
    )
