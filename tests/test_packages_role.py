"""Regression tests for required RPM package task definitions."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_TASKS = REPO_ROOT / "ansible/roles/packages/tasks/main.yml"


def test_system_packages_include_ninja_build() -> None:
    """Ensure Meson/CMake projects can rely on Ninja being present."""
    tasks_content = PACKAGES_TASKS.read_text()

    assert "- ninja-build" in tasks_content, (
        "packages role must install the Fedora Ninja package"
    )
