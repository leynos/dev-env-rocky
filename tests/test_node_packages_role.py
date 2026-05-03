"""Regression tests for globally installed Node package task definitions."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_PACKAGES_TASKS = REPO_ROOT / "ansible/roles/node_packages/tasks/main.yml"
BUN_PACKAGES_INF = REPO_ROOT / "bun-packages.inf"


def extract_task(content: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^- name: {re.escape(name)}\n(?P<body>.*?)(?=^- name: |\Z)", content
    )
    assert match, f"expected task named {name!r} to exist"
    return match.group("body")


def test_firecrawl_mcp_is_installed_globally() -> None:
    tasks_content = NODE_PACKAGES_TASKS.read_text()
    package_list = BUN_PACKAGES_INF.read_text()

    assert 'name: "firecrawl-mcp"' in tasks_content, (
        "node_packages must install the firecrawl-mcp executable globally"
    )
    assert "firecrawl-mcp" in package_list, (
        "bun-packages.inf must document the firecrawl-mcp global package"
    )


def test_firecrawl_mcp_is_linked_into_local_bin() -> None:
    tasks_content = NODE_PACKAGES_TASKS.read_text()
    task = extract_task(tasks_content, "Link firecrawl-mcp into ~/.local/bin")

    assert 'src: "{{ ansible_env.HOME }}/.bun/bin/firecrawl-mcp"' in task, (
        "node_packages must link from the Bun global firecrawl-mcp executable"
    )
    assert 'dest: "{{ ansible_env.HOME }}/.local/bin/firecrawl-mcp"' in task, (
        "node_packages must create the firecrawl-mcp command in ~/.local/bin"
    )
    assert "state: link" in task, (
        "node_packages must create a symlink, not copy the firecrawl-mcp executable"
    )
    assert "force: true" in task, (
        "node_packages must repair an existing incorrect firecrawl-mcp path"
    )
