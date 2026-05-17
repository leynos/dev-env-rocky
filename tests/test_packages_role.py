"""Regression tests for the packages Ansible role.

Validates that the RPM package install task enumerates all prerequisites
required by dependent roles. Specifically, asserts that ``git`` and
``unzip`` are declared for installation so that the ``coderabbit_cli``
role's vendored installer script can run without network-sourced package
installation at converge time. Tests parse the task YAML structurally
rather than matching raw text, ensuring assertion failures point to the
correct module parameter rather than incidental file content.
"""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]  # ty: ignore[unresolved-import]

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_TASKS = REPO_ROOT / "ansible/roles/packages/tasks/main.yml"


def load_packages_tasks() -> list[dict[str, Any]]:
    """Load the package role task list as structured YAML."""
    tasks = yaml.safe_load(PACKAGES_TASKS.read_text(encoding="utf-8"))
    assert isinstance(tasks, list), "packages role tasks must be a YAML list"

    return tasks


def find_task(tasks: list[dict[str, Any]], task_name: str) -> dict[str, Any]:
    """Return the named Ansible task from the parsed task list."""
    for task in tasks:
        if task.get("name") == task_name:
            return task

    raise AssertionError(f"expected task {task_name!r} to exist")


def system_package_task() -> dict[str, Any]:
    """Return the structured RPM package installation task."""
    return find_task(load_packages_tasks(), "Install system packages (RPM)")


def assert_required_system_package(package_name: str) -> None:
    """Ensure a package is installed by the RPM package task."""
    task = system_package_task()
    dnf_config = task.get("ansible.builtin.dnf")
    assert isinstance(dnf_config, dict), (
        "system package task must use ansible.builtin.dnf"
    )

    package_names = dnf_config.get("name")
    assert isinstance(package_names, list), (
        "system package task must pass a list to ansible.builtin.dnf.name"
    )
    assert package_name in package_names, f"packages role must install {package_name}"
    assert dnf_config.get("state") == "present", (
        "system package task must install packages with state: present"
    )
    assert task.get("become") is True, "system package task must escalate privileges"


def test_system_packages_include_ninja_build() -> None:
    """Ensure Meson/CMake projects can rely on Ninja being present."""
    assert_required_system_package("ninja-build")


def test_system_packages_include_coderabbit_installer_prerequisites() -> None:
    """Ensure the CodeRabbit installer has its required RPM tools.

    Parses tasks/main.yml as YAML and inspects the ``name`` list of the
    DNF install task to assert ``git`` and ``unzip`` are present.
    """
    assert_required_system_package("git")
    assert_required_system_package("unzip")


def test_system_packages_include_htop() -> None:
    """Ensure deployed systems include an interactive process viewer."""
    assert_required_system_package("htop")
