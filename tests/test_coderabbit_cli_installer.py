"""Behavioural tests for the checked-in CodeRabbit CLI installer."""

import re
import stat
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest  # type: ignore[import-untyped]  # ty: ignore[unresolved-import]

REPO_ROOT = Path(__file__).resolve().parents[1]
CODERABBIT_INSTALLER = (
    REPO_ROOT / "ansible/roles/coderabbit_cli/files/coderabbit-install.sh"
)


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
    tmp_path: Path,
    release_root: Path,
    download_retries: str = "1",
    install_dir: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the checked-in installer against a local release fixture."""
    env = {
        "CODERABBIT_DOWNLOAD_RETRIES": download_retries,
        "CODERABBIT_DOWNLOAD_URL": release_root.as_uri(),
        "CODERABBIT_INSTALL_DIR": install_dir or str(tmp_path / "home/.local/bin"),
        "HOME": str(tmp_path / "home"),
        "NO_COLOR": "1",
        "PATH": "/usr/bin:/bin",
    }
    return subprocess.run(  # noqa: S603, RUF100
        # The checked-in installer path and fully controlled env isolate the test.
        ["/bin/sh", str(CODERABBIT_INSTALLER)],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


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
        ), f"missing log for stage={stage} message={message}"
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


@pytest.mark.parametrize(
    ("retry_value", "retry_count"),
    [("invalid", "3"), ("0", "1"), ("-2", "1")],
)
def test_installer_normalizes_invalid_download_retries(
    tmp_path: Path, retry_value: str, retry_count: str
) -> None:
    """Installer must return clear failures for invalid retry settings."""
    release_root = tmp_path / f"releases-{retry_value}"
    install_root = tmp_path / retry_value
    (release_root / "latest").mkdir(parents=True)
    install_root.mkdir()
    (release_root / "latest/VERSION").write_text("v0.0.0-test\n", encoding="utf-8")

    result = run_installer(install_root, release_root, retry_value)

    assert result.returncode != 0
    assert "stage=download" in result.stderr
    assert f"retry_count={retry_count}" in result.stderr


@pytest.mark.parametrize("collision_name", ["coderabbit", "cr"])
def test_installer_rejects_directory_collisions(
    tmp_path: Path, collision_name: str
) -> None:
    """Installer must fail before publishing into target directories."""
    release_root = tmp_path / "releases"
    install_dir = tmp_path / "home/.local/bin"
    write_release_fixture(release_root)
    (install_dir / collision_name).mkdir(parents=True)

    result = run_installer(tmp_path, release_root)

    assert result.returncode != 0
    assert "stage=install" in result.stderr
    assert "level=error" in result.stderr
    assert f"{collision_name}" in result.stderr


def test_installer_rejects_unresolved_user_home(tmp_path: Path) -> None:
    """Installer must fail instead of using literal unresolved ~user paths."""
    release_root = tmp_path / "releases"
    write_release_fixture(release_root)

    result = run_installer(
        tmp_path,
        release_root,
        install_dir="~coderabbit_missing_user/.local/bin",
    )

    assert result.returncode != 0
    assert "Could not resolve home directory for user" in result.stderr
    assert not (tmp_path / "~coderabbit_missing_user").exists()


def test_installer_reports_extract_failure(tmp_path: Path) -> None:
    """Installer must not report extract success for corrupt archives."""
    release_root = tmp_path / "releases"
    latest = release_root / "latest"
    latest.mkdir(parents=True)
    (latest / "VERSION").write_text("v0.0.0-test\n", encoding="utf-8")
    (latest / "coderabbit-linux-x64.zip").write_text(
        "not a zip archive\n", encoding="utf-8"
    )

    result = run_installer(tmp_path, release_root)

    assert result.returncode != 0
    assert "Failed to extract CodeRabbit CLI archive" in result.stderr
    assert "stage=extract" in result.stderr
    assert "level=error" in result.stderr
    assert "extracted CodeRabbit CLI archive" not in result.stderr


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
        subprocess.Popen(  # noqa: S603, RUF100
            # The checked-in installer path and fully controlled env isolate the test.
            ["/bin/sh", str(CODERABBIT_INSTALLER)],
            cwd=tmp_path,
            env=installer_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as first,
        subprocess.Popen(  # noqa: S603, RUF100
            # The checked-in installer path and fully controlled env isolate the test.
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
