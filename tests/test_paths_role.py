"""Tests for managed user PATH normalisation."""

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PATHS_TEMPLATE = REPO_ROOT / "ansible/roles/paths/templates/00-paths.j2"
PATHS_TASKS = REPO_ROOT / "ansible/roles/paths/tasks/main.yml"
SETUP_PATHS = REPO_ROOT / "bin/setup-paths"


def run_bash(tmp_path: Path, script: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")
    env.pop("BASH_ENV", None)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def create_managed_path_directories(home: Path) -> None:
    for relative_path in (".local/bin", ".cargo/bin", ".bun/bin", "go/bin"):
        (home / relative_path).mkdir(parents=True)


def expected_normalised_path(home: Path) -> str:
    return (
        f"{home}/.local/bin:"
        f"{home}/.cargo/bin:"
        f"{home}/.bun/bin:"
        f"{home}/go/bin:"
        "/usr/bin:/bin"
    )


def assert_path_is_normalised(actual_path: str, home: Path) -> None:
    expected_path = expected_normalised_path(home)
    assert actual_path == expected_path, (
        f"expected managed PATH {expected_path!r}, got {actual_path!r}"
    )
    assert actual_path.count(f"{home}/.bun/bin") == 1, (
        f"expected one managed Bun bin entry, got {actual_path!r}"
    )


def test_paths_template_moves_managed_directories_to_documented_prefix(
    tmp_path: Path,
) -> None:
    create_managed_path_directories(tmp_path)

    result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        PATH="$HOME/.bun/bin:$HOME/.local/bin:/usr/bin:$HOME/.bun/bin:/bin"
        source {PATHS_TEMPLATE}
        printf '%s\\n' "$PATH"
        """,
    )

    assert result.returncode == 0, f"00-paths template failed: {result.stderr}"
    assert_path_is_normalised(result.stdout.strip(), tmp_path)


def test_setup_paths_generates_normalising_script(tmp_path: Path) -> None:
    create_managed_path_directories(tmp_path)

    generate_result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        {SETUP_PATHS}
        """,
    )

    assert generate_result.returncode == 0, (
        f"setup-paths failed: {generate_result.stderr}"
    )

    generated_script = tmp_path / ".bashrc.d/00-paths"
    source_result = run_bash(
        tmp_path,
        f"""
        set -euo pipefail
        PATH="$HOME/.bun/bin:$HOME/.local/bin:/usr/bin:$HOME/.bun/bin:/bin"
        source {generated_script}
        printf '%s\\n' "$PATH"
        """,
    )

    assert source_result.returncode == 0, (
        f"generated 00-paths failed: {source_result.stderr}"
    )
    assert_path_is_normalised(source_result.stdout.strip(), tmp_path)


def test_paths_role_sources_normaliser_at_end_of_bash_profile() -> None:
    tasks = PATHS_TASKS.read_text()

    assert "- name: Ensure .bash_profile re-sources managed PATH at EOF" in tasks, (
        "paths role must add an EOF hook for login shells"
    )
    assert 'path: "{{ ansible_env.HOME }}/.bash_profile"' in tasks, (
        "paths role must manage .bash_profile, where Bun installer blocks run"
    )
    assert "[ -f ~/.bashrc.d/00-paths ] && . ~/.bashrc.d/00-paths" in tasks, (
        "paths role must source the managed path normaliser after profile content"
    )
    assert (
        'marker: "# {mark} ANSIBLE MANAGED BLOCK - managed PATH EOF hook"' in tasks
    ), "paths role must use a stable marker for the .bash_profile EOF hook"
    assert "insertafter: EOF" in tasks, (
        "paths role must append the normaliser hook at EOF"
    )
