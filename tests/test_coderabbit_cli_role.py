"""Regression tests for the coderabbit_cli Ansible role.

Verifies role wiring: installer source path, idempotence guards,
vaulted-key authentication, no_log discipline, site.yml ordering,
and Makefile Molecule invocation. Tests load raw YAML/text from the
repository and assert structural correctness without executing Ansible.
"""

import re
import stat
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import yaml  # type: ignore[import-untyped]  # ty: ignore[unresolved-import]

REPO_ROOT = Path(__file__).resolve().parents[1]
CODERABBIT_DEFAULTS = REPO_ROOT / "ansible/roles/coderabbit_cli/defaults/main.yml"
CODERABBIT_INSTALLER = (
    REPO_ROOT / "ansible/roles/coderabbit_cli/files/coderabbit-install.sh"
)
CODERABBIT_TASKS = REPO_ROOT / "ansible/roles/coderabbit_cli/tasks/main.yml"
MAKEFILE = REPO_ROOT / "Makefile"
SITE_PLAYBOOK = REPO_ROOT / "ansible/site.yml"


def flatten_tasks(tasks: list[dict]) -> list[dict]:
    """Return top-level tasks and nested block/rescue/always tasks.

    Recurses into ``block``, ``rescue``, and ``always`` keys. Depth is
    bounded by the nesting depth of the task file, which by Ansible
    convention is shallow (typically one or two levels).
    """
    flattened: list[dict] = []
    for task in tasks:
        flattened.append(task)
        for block_name in ("block", "rescue", "always"):
            flattened.extend(flatten_tasks(task.get(block_name, [])))
    return flattened


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


def write_release_fixture(release_root: Path) -> None:
    """Write a local CodeRabbit release archive for installer tests."""
    latest = release_root / "latest"
    latest.mkdir(parents=True)
    binary = release_root / "coderabbit"
    binary.write_text(
        "#!/usr/bin/env sh\n"
        'if [ "${1:-}" = "-V" ]; then\n'
        "  printf 'coderabbit 0.0.0-test\\n'\n"
        "  exit 0\n"
        "fi\n"
        "printf 'fake coderabbit\\n'\n",
        encoding="utf-8",
    )
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    with ZipFile(latest / "coderabbit-linux-x64.zip", "w", ZIP_DEFLATED) as archive:
        archive.write(binary, "coderabbit")
    (latest / "VERSION").write_text("v0.0.0-test\n", encoding="utf-8")


def run_installer(
    tmp_path: Path, release_root: Path
) -> subprocess.CompletedProcess[str]:
    """Run the checked-in installer against a local release fixture."""
    install_dir = tmp_path / "home/.local/bin"
    env = {
        "CODERABBIT_DOWNLOAD_RETRIES": "1",
        "CODERABBIT_DOWNLOAD_URL": release_root.as_uri(),
        "CODERABBIT_INSTALL_DIR": str(install_dir),
        "HOME": str(tmp_path / "home"),
        "NO_COLOR": "1",
        "PATH": "/usr/bin:/bin",
    }
    return subprocess.run(
        ["/bin/sh", str(CODERABBIT_INSTALLER)],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_coderabbit_cli_role_uses_local_installer_and_is_idempotent() -> None:
    """Role must copy the checked-in installer and guard with creates:."""
    defaults_text = CODERABBIT_DEFAULTS.read_text()
    defaults_data = yaml.safe_load(defaults_text)
    installer_src: str = defaults_data["coderabbit_cli_installer_src"]
    tasks = flatten_tasks(yaml.safe_load(CODERABBIT_TASKS.read_text()))
    install_task = next(t for t in tasks if t.get("name") == "Install CodeRabbit CLI")
    copy_task = next(
        t for t in tasks if t.get("name") == "Copy CodeRabbit CLI installer"
    )

    assert "coderabbit-install.sh" in installer_src, (
        "installer src must reference coderabbit-install.sh"
    )
    assert installer_src == "{{ role_path }}/files/coderabbit-install.sh", (
        "installer src must use the checked-in role files path"
    )
    assert defaults_data["coderabbit_cli_install_dir"] == (
        "{{ coderabbit_cli_home_dir }}/.local/bin"
    ), (
        "install_dir must be derived from coderabbit_cli_home_dir, not ansible_facts.env.HOME"
    )
    assert defaults_data["coderabbit_cli_home_dir"] == "~{{ owner_user }}", (
        "home dir must be derived from owner_user, not ansible_facts.env.HOME"
    )
    assert "lookup(" not in defaults_text, "defaults must not use any lookup() calls"
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
    install_block = extract_task(
        CODERABBIT_TASKS.read_text(), "Install and validate CodeRabbit CLI"
    )
    assert "coderabbit_cli_alias.stat.lnk_source | realpath" in install_block
    assert "coderabbit_cli_install_dir | expanduser" in install_block


def test_coderabbit_cli_role_exports_vaulted_api_key_without_logging() -> None:
    """Auth task must use --api-key with the vaulted key and set no_log."""
    defaults = yaml.safe_load(CODERABBIT_DEFAULTS.read_text())
    tasks = flatten_tasks(yaml.safe_load(CODERABBIT_TASKS.read_text()))
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
    credential_stat_task = next(
        t
        for t in tasks
        if t.get("name") == "Check for existing CodeRabbit CLI auth file"
    )
    auth_command = auth_task["ansible.builtin.shell"]["cmd"]

    assert (
        "coderabbit_api_keys | default({}, true)" in defaults["coderabbit_cli_api_key"]
    )
    assert ".get(inventory_hostname, '')" in defaults["coderabbit_cli_api_key"]
    assert "umask 077" in auth_command
    assert "{{ coderabbit_cli_install_dir }}/coderabbit auth login --api-key" in (
        auth_command
    )
    assert "{{ coderabbit_cli_api_key | quote }}" in auth_command
    assert auth_task["ansible.builtin.shell"]["executable"] == "/bin/bash"
    assert auth_task["args"]["creates"] == (
        "{{ coderabbit_cli_home_dir }}/.coderabbit/auth.json"
    )
    assert auth_task.get("no_log") is True
    assert auth_task["when"] == "coderabbit_cli_api_key | length > 0"
    assert credential_mode_task["ansible.builtin.file"]["path"] == (
        "{{ coderabbit_cli_home_dir }}/.coderabbit/auth.json"
    )
    assert credential_mode_task["ansible.builtin.file"]["owner"] == "{{ owner_user }}"
    assert credential_mode_task["ansible.builtin.file"]["group"] == "{{ owner_user }}"
    assert credential_mode_task["ansible.builtin.file"]["mode"] == "0600"
    assert credential_stat_task["ansible.builtin.stat"]["path"] == (
        "{{ coderabbit_cli_home_dir }}/.coderabbit/auth.json"
    )
    assert credential_stat_task["register"] == "coderabbit_cli_auth_file"
    assert "coderabbit_cli_auth_file.stat.exists" in credential_mode_task["when"], (
        "permission task must be gated on auth file existence, not API key presence"
    )


def test_coderabbit_cli_role_creates_private_auth_directory() -> None:
    """Auth directory must exist with private permissions before login."""
    tasks = flatten_tasks(yaml.safe_load(CODERABBIT_TASKS.read_text()))
    auth_dir_task = next(
        task
        for task in tasks
        if task.get("name") == "Ensure CodeRabbit CLI auth directory exists"
    )
    file_args = auth_dir_task["ansible.builtin.file"]

    assert file_args["path"] == "{{ coderabbit_cli_home_dir }}/.coderabbit"
    assert file_args["state"] == "directory"
    assert file_args["owner"] == "{{ owner_user }}"
    assert file_args["group"] == "{{ owner_user }}"
    assert file_args["mode"] == "0700"
    assert auth_dir_task["when"] == "coderabbit_cli_api_key | length > 0"


def test_coderabbit_cli_api_key_defaults_to_empty_for_missing_host() -> None:
    """API key expression must skip authentication when no host key exists."""
    defaults = yaml.safe_load(CODERABBIT_DEFAULTS.read_text())
    expression = defaults["coderabbit_cli_api_key"]

    assert "default({}, true)" in expression
    assert ".get(inventory_hostname, '')" in expression
    assert "default(omit)" not in expression


def test_coderabbit_cli_role_reports_install_diagnostics() -> None:
    """Install block must expose stdout and stderr when installation fails."""
    task_body = extract_task(
        CODERABBIT_TASKS.read_text(), "Install and validate CodeRabbit CLI"
    )

    assert "block:" in task_body
    assert "rescue:" in task_body
    assert "coderabbit_cli_install_result.stderr" in task_body
    assert "coderabbit_cli_install_result.stdout" in task_body
    assert "Assert CodeRabbit CLI install invariants" in task_body
    assert "coderabbit_cli_binary.stat.executable" in task_body


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


def test_molecule_verify_asserts_coderabbit_output_and_state() -> None:
    """Molecule verify must cover output, permissions, ownership, and idempotence."""
    verify_path = REPO_ROOT / "ansible/roles/coderabbit_cli/molecule/rocky10/verify.yml"
    verify_content = verify_path.read_text()

    assert "[INFO] Platform: linux-x64" in verify_content
    assert "[SUCCESS] Installation verified" in verify_content
    assert "molecule-coderabbit-token' not in" in verify_content
    assert "coderabbit_auth_file.stat.mode == '0600'" in verify_content
    assert "coderabbit_auth_file.stat.pw_name == verify_owner_user" in verify_content
    assert 'owner_user: "{{ verify_owner_user }}"' in verify_content
    assert 'coderabbit_cli_home_dir: "{{ verify_home_dir }}"' in verify_content
    assert "Rerun CodeRabbit CLI role again to verify idempotence" in verify_content
    assert "coderabbit_cli_install_result is not changed" in verify_content


def test_installer_logs_retry_attempts_timing_and_state(tmp_path: Path) -> None:
    """Installer must emit structured retry, timing, and stage details."""
    release_root = tmp_path / "releases"
    write_release_fixture(release_root)

    result = run_installer(tmp_path, release_root)

    assert result.returncode == 0, result.stdout + result.stderr
    for stage, message in (
        ("download", "attempt 1 for CodeRabbit CLI artifact"),
        ("download", "completed CodeRabbit CLI artifact download"),
        ("extract", "extracted CodeRabbit CLI archive"),
        ("install", "published CodeRabbit CLI binary and alias"),
        ("install", "completed CodeRabbit CLI install"),
    ):
        assert re.search(
            rf"stage={stage} level=info duration_ms=\d+ retry_count=0 "
            rf'message="{message}"',
            result.stderr,
        )
    assert release_root.as_uri() not in result.stderr


def test_installer_publishes_binary_and_alias_atomically(tmp_path: Path) -> None:
    """Installer must replace binary and alias from same-directory temp paths."""
    release_root = tmp_path / "releases"
    install_dir = tmp_path / "home/.local/bin"
    old_alias_target = tmp_path / "home/.local/bin/old-coderabbit"
    write_release_fixture(release_root)
    install_dir.mkdir(parents=True)
    (install_dir / "coderabbit").write_text("stale binary\n", encoding="utf-8")
    old_alias_target.write_text("stale alias target\n", encoding="utf-8")
    (install_dir / "cr").symlink_to(old_alias_target)

    result = run_installer(tmp_path, release_root)
    install_path = install_dir / "coderabbit"
    alias_path = install_dir / "cr"

    assert result.returncode == 0, result.stdout + result.stderr
    assert install_path.is_file()
    assert install_path.stat().st_mode & stat.S_IXUSR
    assert "fake coderabbit" in install_path.read_text(encoding="utf-8")
    assert alias_path.is_symlink()
    assert alias_path.resolve() == install_path
    assert alias_path.resolve() != old_alias_target
    assert 'message="published CodeRabbit CLI binary and alias"' in result.stderr
    assert 'message="completed CodeRabbit CLI install"' in result.stderr


def test_installer_reports_download_failure(tmp_path: Path) -> None:
    """Installer must fail clearly when an archive cannot be downloaded."""
    release_root = tmp_path / "releases"
    (release_root / "latest").mkdir(parents=True)
    (release_root / "latest/VERSION").write_text("v0.0.0-test\n", encoding="utf-8")

    result = run_installer(tmp_path, release_root)

    assert result.returncode != 0
    assert "stage=download" in result.stderr
    assert "level=error" in result.stderr
    assert "retry_count=1" in result.stderr
    assert release_root.as_uri() not in result.stderr


def test_installer_succeeds_under_concurrent_execution(tmp_path: Path) -> None:
    """Concurrent installer runs must leave a valid binary and alias."""
    release_root = tmp_path / "releases"
    write_release_fixture(release_root)

    installer_env = {
        "CODERABBIT_DOWNLOAD_RETRIES": "1",
        "CODERABBIT_DOWNLOAD_URL": release_root.as_uri(),
        "CODERABBIT_INSTALL_DIR": str(tmp_path / "home/.local/bin"),
        "HOME": str(tmp_path / "home"),
        "NO_COLOR": "1",
        "PATH": "/usr/bin:/bin",
    }
    with (
        subprocess.Popen(
            ["/bin/sh", str(CODERABBIT_INSTALLER)],
            cwd=tmp_path,
            env=installer_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as first,
        subprocess.Popen(
            ["/bin/sh", str(CODERABBIT_INSTALLER)],
            cwd=tmp_path,
            env=installer_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as second,
    ):
        first_stdout, first_stderr = first.communicate(timeout=30)
        second_stdout, second_stderr = second.communicate(timeout=30)
    install_dir = tmp_path / "home/.local/bin"

    assert first.returncode == 0, first_stdout + first_stderr
    assert second.returncode == 0, second_stdout + second_stderr
    assert (install_dir / "coderabbit").is_file()
    assert (install_dir / "coderabbit").stat().st_mode & stat.S_IXUSR
    assert (install_dir / "cr").is_symlink()
    assert (install_dir / "cr").resolve() == install_dir / "coderabbit"
