"""Regression tests for globally installed Node package task definitions."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_PACKAGES_TASKS = REPO_ROOT / "ansible/roles/node_packages/tasks/main.yml"
NODE_PACKAGES_DEFAULTS = REPO_ROOT / "ansible/roles/node_packages/defaults/main.yml"
BUN_PACKAGES_INF = REPO_ROOT / "bun-packages.inf"


def extract_task(content: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^- name: {re.escape(name)}\n(?P<body>.*?)(?=^- name: |\Z)", content
    )
    assert match, f"expected task named {name!r} to exist"
    return match.group("body")


def extract_loop_item(content: str, package_name: str) -> str:
    match = re.search(
        rf'(?ms)^    - name: "{re.escape(package_name)}"\n'
        rf"(?P<body>.*?)(?=^    - name: |\Z)",
        content,
    )
    assert match, f"expected package {package_name!r} to exist in the Bun loop"
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


def test_trusted_bun_packages_document_postinstall_reason() -> None:
    tasks_content = NODE_PACKAGES_TASKS.read_text()
    task = extract_task(tasks_content, "Install Node packages globally via bun")

    trusted_packages = re.findall(
        r'(?ms)^    - name: "([^"]+)"\n(?:(?!^    - name: ).)*?'
        r"^      trust_postinstall: true$",
        task,
    )

    assert trusted_packages, "expected at least one trusted Bun package"
    for package_name in trusted_packages:
        package = extract_loop_item(task, package_name)
        reason_match = re.search(
            r"^      trust_postinstall_reason: (?P<reason>.+)$",
            package,
            re.MULTILINE,
        )
        reason = reason_match.group("reason").strip() if reason_match else None
        assert isinstance(reason, str) and reason.strip("\"'").strip(), (
            f"{package_name} trust_postinstall_reason must be a non-empty string"
        )
        version_is_pinned = re.search(
            r'^      version: "[^"]+"$', package, re.MULTILINE
        )
        git_spec_is_pinned = re.search(
            r'^      spec: "git\+https://[^"]+#[0-9a-f]{40}"$',
            package,
            re.MULTILINE,
        )
        assert version_is_pinned or git_spec_is_pinned, (
            f"{package_name} must pin the trusted package version or git commit"
        )


def test_bun_trust_postinstall_uses_boolean_filter() -> None:
    tasks_content = NODE_PACKAGES_TASKS.read_text()
    task = extract_task(tasks_content, "Install Node packages globally via bun")

    assert (
        'trust_postinstall: "{{ item.trust_postinstall | default(false) | bool }}"'
        in task
    )
    assert 'version: "{{ item.version | default(omit) }}"' in task
    assert 'spec: "{{ item.spec | default(omit) }}"' in task


def test_css_view_installs_from_pinned_git_spec_with_browser_postinstall() -> None:
    tasks_content = NODE_PACKAGES_TASKS.read_text()
    package_list = BUN_PACKAGES_INF.read_text()
    task = extract_task(tasks_content, "Install Node packages globally via bun")
    css_view = extract_loop_item(task, "css-view")

    assert (
        "git+https://github.com/leynos/css-view#26b79e8ab739b7a8bcd80341ae7fc2d18600ce85"
        in css_view
    ), "css-view must install from the pinned Leynos GitHub repository commit"
    assert "trust_postinstall: true" in css_view, (
        "css-view postinstall must be trusted so Playwright downloads browsers"
    )
    assert "Chromium" in css_view, (
        "css-view trust reason must document the Chromium browser download"
    )
    assert (
        "git+https://github.com/leynos/css-view#26b79e8ab739b7a8bcd80341ae7fc2d18600ce85"
        in package_list
    ), "bun-packages.inf must document the css-view global package"


def test_optional_browser_and_acp_packages_are_gated() -> None:
    tasks_content = NODE_PACKAGES_TASKS.read_text()
    defaults_content = NODE_PACKAGES_DEFAULTS.read_text()

    puppeteer = extract_loop_item(tasks_content, "puppeteer")
    acp_extension = extract_loop_item(
        tasks_content, "@zed-industries/codex-acp-linux-x64"
    )

    assert "dev_env_install_puppeteer: false" in defaults_content
    assert "dev_env_install_acp_extension_codex: false" in defaults_content
    assert "acp-extension-codex-linux-x64" not in tasks_content
    assert 'enabled: "{{ dev_env_install_puppeteer | default(false) | bool }}"' in (
        puppeteer
    )
    assert "dev_env_install_acp_extension_codex | default(false) | bool" in (
        acp_extension
    )
    assert "ansible_facts['system'] == 'Linux'" in acp_extension
    assert "ansible_facts['architecture'] == 'x86_64'" in acp_extension
