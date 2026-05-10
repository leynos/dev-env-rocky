"""Regression tests for the coderabbit_cli Ansible role.

Verifies role wiring: installer source path, idempotence guards,
vaulted-key authentication, no_log discipline, site.yml ordering,
and Makefile Molecule invocation. Tests load raw YAML/text from the
repository and assert structural correctness without executing Ansible.
"""

import re
from pathlib import Path

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


def test_coderabbit_cli_role_uses_local_installer_and_is_idempotent() -> None:
    """Role must copy the checked-in installer and guard with creates:."""
    defaults = CODERABBIT_DEFAULTS.read_text()
    tasks = CODERABBIT_TASKS.read_text()
    install_task = extract_task(tasks, "Install CodeRabbit CLI")

    assert "../../coderabbit-install.sh" in defaults, (
        "CodeRabbit CLI role must source the already-downloaded installer"
    )
    assert "lookup('env', 'PWD')" not in defaults, (
        "installer src must not use ambient PWD; use playbook_dir instead"
    )
    assert "https://cli.coderabbit.ai/releases" in defaults, (
        "CodeRabbit CLI role must pass a real default release URL, not omit"
    )
    assert 'src: "{{ coderabbit_cli_installer_src }}"' in tasks, (
        "CodeRabbit CLI role must copy the configured installer source"
    )
    assert 'creates: "{{ coderabbit_cli_install_dir }}/coderabbit"' in install_task, (
        "CodeRabbit CLI installer must be idempotent around the installed binary"
    )
    assert "CODERABBIT_INSTALL_DIR" in install_task, (
        "CodeRabbit CLI installer must target the managed user-local bin directory"
    )
    assert "default(omit)" not in install_task, (
        "omit must not be used inside task environment because it becomes a string"
    )


def test_coderabbit_cli_role_exports_vaulted_api_key_without_logging() -> None:
    """Auth task must use --api-key with the vaulted key and set no_log."""
    defaults = CODERABBIT_DEFAULTS.read_text()
    tasks = CODERABBIT_TASKS.read_text()
    task = extract_task(tasks, "Authenticate CodeRabbit CLI with vaulted API key")

    assert (
        'coderabbit_cli_api_key: "{{ coderabbit_api_keys[inventory_hostname] }}"'
        in defaults
    )
    assert "auth" in task
    assert "login" in task
    assert "--api-key" in task
    assert "{{ coderabbit_cli_api_key }}" in task
    assert 'creates: "{{ ansible_facts.env.HOME }}/.coderabbit/auth.json"' in task
    assert "no_log: true" in task, (
        "CodeRabbit auth task must suppress secret-bearing command output"
    )


def test_site_runs_coderabbit_cli_before_agent_tools() -> None:
    """coderabbit_cli must precede agent_tools in site.yml role list."""
    content = SITE_PLAYBOOK.read_text()

    assert content.index("    - coderabbit_cli") < content.index("    - agent_tools"), (
        "CodeRabbit CLI must be installed before agent_tools runs"
    )


def test_make_molecule_runs_coderabbit_cli_scenario() -> None:
    """Makefile molecule target must invoke the rocky10 scenario."""
    content = MAKEFILE.read_text()

    assert "cd ansible/roles/coderabbit_cli &&" in content
    assert "$(MOLECULE) test -s rocky10" in content
