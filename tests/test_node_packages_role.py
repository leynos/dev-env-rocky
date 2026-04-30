"""Regression tests for globally installed Node package task definitions."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_PACKAGES_TASKS = REPO_ROOT / "ansible/roles/node_packages/tasks/main.yml"
BUN_PACKAGES_INF = REPO_ROOT / "bun-packages.inf"


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

    assert "Link firecrawl-mcp into ~/.local/bin" in tasks_content, (
        "node_packages must expose firecrawl-mcp through the standard local bin path"
    )
    assert 'src: "{{ ansible_env.HOME }}/.bun/bin/firecrawl-mcp"' in tasks_content, (
        "node_packages must link from the Bun global firecrawl-mcp executable"
    )
    assert 'dest: "{{ ansible_env.HOME }}/.local/bin/firecrawl-mcp"' in tasks_content, (
        "node_packages must create the firecrawl-mcp command in ~/.local/bin"
    )
