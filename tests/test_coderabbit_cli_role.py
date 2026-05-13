"""Regression tests for the coderabbit_cli Ansible role.

Verifies role wiring: installer source path, idempotence guards,
vaulted-key authentication, no_log discipline, site.yml ordering,
and Makefile Molecule invocation. Tests load raw YAML/text from the
repository and assert structural correctness without executing Ansible.
"""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CODERABBIT_DEFAULTS = REPO_ROOT / "ansible/roles/coderabbit_cli/defaults/main.yml"
CODERABBIT_TASKS = REPO_ROOT / "ansible/roles/coderabbit_cli/tasks/main.yml"
MAKEFILE = REPO_ROOT / "Makefile"
SITE_PLAYBOOK = REPO_ROOT / "ansible/site.yml"


def extract_task(content: str, name: str) -> str:
    """Return the YAML body of the task identified by *name*.

    Scans *content* (a raw tasks YAML string) for a ``- name: <name>``
    header and returns everything up to the next task header or end of
    string. Raises ``AssertionError`` if no matching task is found.
    """
    match = re.search(
        rf"(?ms)^- name: {re.escape(name)}\n(?P<body>.*?)(?=^- name: |\Z)", content
    )
    assert match, f"expected task named {name!r} to exist"
    return match.group("body")


def extract_make_target(content: str, name: str) -> str:
    """Return the recipe body for the Makefile target named *name*."""
    match = re.search(
        rf"(?ms)^{re.escape(name)}:[^\n]*\n(?P<body>.*?)(?=^[^\t\n][^:\n]*:|\Z)",
        content,
    )
    assert match, f"expected Makefile target named {name!r} to exist"
    return match.group("body")


def test_coderabbit_cli_role_uses_local_installer_and_is_idempotent() -> None:
    """Role must copy the checked-in installer and guard with creates:."""
    defaults_data = yaml.safe_load(CODERABBIT_DEFAULTS.read_text())
    installer_src: str = defaults_data["coderabbit_cli_installer_src"]
    tasks = yaml.safe_load(CODERABBIT_TASKS.read_text())
    install_task = next(t for t in tasks if t.get("name") == "Install CodeRabbit CLI")
    copy_task = next(
        t for t in tasks if t.get("name") == "Copy CodeRabbit CLI installer"
    )

    assert "../../../" not in installer_src, (
        "installer src must not escape the repository via ../../.."
    )
    assert "coderabbit-install.sh" in installer_src, (
        "installer src must reference coderabbit-install.sh"
    )
    assert installer_src.startswith("{{ playbook_dir }}/"), (
        "installer src must use playbook_dir, not an ambient variable"
    )
    # Verify the path stays within one level above ansible/ (the repo root).
    # playbook_dir resolves to ansible/; one `../` reaches the repo root.
    # Two or more `../` sequences escape the repository.
    traversal_depth = installer_src.count("../")
    assert traversal_depth == 1, (
        f"installer src must ascend exactly one directory level from playbook_dir "
        f"(repo root); found {traversal_depth} '../' sequences in {installer_src!r}"
    )
    assert "lookup" not in yaml.dump(defaults_data), (
        "defaults must not use any lookup() calls"
    )
    assert (
        defaults_data["coderabbit_cli_download_url"]
        == "https://cli.coderabbit.ai/releases"
    )
    assert (
        copy_task["ansible.builtin.copy"]["src"] == "{{ coderabbit_cli_installer_src }}"
    )
    assert (
        install_task["args"]["creates"] == "{{ coderabbit_cli_install_dir }}/coderabbit"
    )
    env = install_task["environment"]
    assert "CODERABBIT_INSTALL_DIR" in env
    assert "default(omit)" not in str(env)


def test_coderabbit_cli_role_exports_vaulted_api_key_without_logging() -> None:
    """Auth task must use --api-key with the vaulted key and set no_log."""
    defaults = yaml.safe_load(CODERABBIT_DEFAULTS.read_text())
    tasks = yaml.safe_load(CODERABBIT_TASKS.read_text())
    auth_task = next(
        t
        for t in tasks
        if t.get("name") == "Authenticate CodeRabbit CLI with vaulted API key"
    )
    credential_mode_task = next(
        t
        for t in tasks
        if t.get("name") == "Restrict CodeRabbit CLI credential file permissions"
    )
    argv = auth_task["ansible.builtin.command"]["argv"]

    assert (
        "coderabbit_api_keys | default({}, true)" in defaults["coderabbit_cli_api_key"]
    )
    assert ".get(inventory_hostname, '')" in defaults["coderabbit_cli_api_key"]
    assert "auth" in argv
    assert "login" in argv
    assert "--api-key" in argv
    assert "{{ coderabbit_cli_api_key }}" in argv
    assert auth_task["args"]["creates"] == (
        "{{ ansible_facts.env.HOME }}/.coderabbit/auth.json"
    )
    assert auth_task.get("no_log") is True
    assert auth_task["when"] == "coderabbit_cli_api_key | length > 0"
    assert credential_mode_task["ansible.builtin.file"]["path"] == (
        "{{ ansible_facts.env.HOME }}/.coderabbit/auth.json"
    )
    assert credential_mode_task["ansible.builtin.file"]["owner"] == "{{ owner_user }}"
    assert credential_mode_task["ansible.builtin.file"]["group"] == "{{ owner_user }}"
    assert credential_mode_task["ansible.builtin.file"]["mode"] == "0600"
    assert credential_mode_task["when"] == "coderabbit_cli_api_key | length > 0"


def test_site_runs_coderabbit_cli_before_agent_tools() -> None:
    """coderabbit_cli must precede agent_tools in site.yml role list."""
    plays = yaml.safe_load(SITE_PLAYBOOK.read_text())
    user_play = next(
        play
        for play in plays
        if play.get("name") == "Configure user environment for owner user"
    )
    roles = user_play["roles"]

    assert "coderabbit_cli" in roles
    assert "agent_tools" in roles
    assert roles.index("coderabbit_cli") < roles.index("agent_tools")


def test_make_molecule_runs_coderabbit_cli_scenario() -> None:
    """Makefile molecule target must invoke the rocky10 scenario."""
    target_body = extract_make_target(MAKEFILE.read_text(), "molecule")

    assert "cd ansible/roles/coderabbit_cli &&" in target_body
    assert "$(MOLECULE) test -s rocky10" in target_body
