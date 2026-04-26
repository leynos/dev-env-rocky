"""Unit tests for rust_cleanup.

These tests validate directory skipping, cache marker detection, stale-file
checks, target discovery, deletion behaviour, and command-line entrypoint
handling for the ``rust_cleanup`` package.

Usage
-----
Run the full package suite:

    uv run --project python/rust_cleanup --python 3.12 pytest python/rust_cleanup/tests

Run only the CLI tests:

    uv run --project python/rust_cleanup --python 3.12 pytest \
        python/rust_cleanup/tests/test_rust_cleanup.py::TestMain
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest import mock

import pytest

from rust_cleanup import (
    CACHEDIR_TAG,
    CleanupError,
    CUTOFF_SECONDS,
    TARGET_DIR,
    cleanup_target_dirs,
    delete_directory,
    find_target_dirs,
    has_recent_files,
    is_cache_dir,
    main,
    should_skip_dir,
)


def assert_equal(actual: object, expected: object, context: str) -> None:
    assert actual == expected, f"{context}: expected {expected!r}, got {actual!r}"


def assert_is(actual: object, expected: object, context: str) -> None:
    assert actual is expected, f"{context}: expected {expected!r}, got {actual!r}"


class TestShouldSkipDir:
    """Tests for should_skip_dir."""

    @pytest.mark.parametrize(
        ("dirname", "expected"),
        [
            (".git", True),
            ("node_modules", True),
            (".svn", True),
            (".hg", True),
            ("__pycache__", True),
            (".pytest_cache", True),
            ("target", False),
            ("src", False),
        ],
    )
    def test_should_skip_dir_parametrized(self, dirname: str, expected: bool) -> None:
        assert_is(
            should_skip_dir(dirname),
            expected,
            f"should_skip_dir should classify {dirname}",
        )


class TestIsCacheDir:
    """Tests for is_cache_dir."""

    def test_returns_true_when_cachedir_tag_exists(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / CACHEDIR_TAG).touch()
        assert_is(
            is_cache_dir(cache_dir),
            True,
            "is_cache_dir should accept CACHEDIR.TAG file",
        )

    def test_returns_false_when_cachedir_tag_missing(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        assert_is(
            is_cache_dir(cache_dir), False, "is_cache_dir should reject missing tag"
        )

    def test_returns_false_when_cachedir_tag_is_directory(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / CACHEDIR_TAG).mkdir()
        assert_is(
            is_cache_dir(cache_dir), False, "is_cache_dir should reject tag directory"
        )


class TestHasRecentFiles:
    """Tests for has_recent_files."""

    def test_returns_true_for_recent_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "recent.txt"
        test_file.write_text("content")
        current_time = time.time()
        cutoff_time = current_time - CUTOFF_SECONDS
        assert_is(
            has_recent_files(tmp_path, cutoff_time),
            True,
            "has_recent_files should detect recent file",
        )

    def test_returns_false_for_old_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "old.txt"
        test_file.write_text("content")
        old_time = time.time() - (CUTOFF_SECONDS + 3600)
        os.utime(test_file, (old_time, old_time))
        cutoff_time = time.time() - CUTOFF_SECONDS
        assert_is(
            has_recent_files(tmp_path, cutoff_time),
            False,
            "has_recent_files should ignore old file",
        )

    def test_returns_false_for_empty_directory(self, tmp_path: Path) -> None:
        cutoff_time = time.time() - CUTOFF_SECONDS
        assert_is(
            has_recent_files(tmp_path, cutoff_time),
            False,
            "has_recent_files should reject empty directory",
        )

    def test_checks_nested_files(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        test_file = nested / "deep.txt"
        test_file.write_text("content")
        cutoff_time = time.time() - CUTOFF_SECONDS
        assert_is(
            has_recent_files(tmp_path, cutoff_time),
            True,
            "has_recent_files should check nested files",
        )

    def test_skips_noisy_directories(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        test_file = git_dir / "recent.txt"
        test_file.write_text("content")
        cutoff_time = time.time() - CUTOFF_SECONDS
        assert_is(
            has_recent_files(tmp_path, cutoff_time),
            False,
            "has_recent_files should skip noisy directories",
        )

    def test_handles_missing_file_gracefully(self, tmp_path: Path) -> None:
        test_file = tmp_path / "temp.txt"
        test_file.write_text("content")
        cutoff_time = time.time() - CUTOFF_SECONDS
        test_file.unlink()
        assert_is(
            has_recent_files(tmp_path, cutoff_time),
            False,
            "has_recent_files should tolerate missing files",
        )


class TestDeleteDirectory:
    """Tests for delete_directory."""

    def test_deletes_directory_and_contents(self, tmp_path: Path) -> None:
        target = tmp_path / "to_delete"
        target.mkdir()
        (target / "file.txt").write_text("content")
        (target / "subdir").mkdir()
        (target / "subdir" / "another.txt").write_text("more content")

        assert_is(
            delete_directory(target),
            True,
            "delete_directory should delete existing directory",
        )
        assert not target.exists(), "delete_directory should remove directory contents"

    def test_raises_for_nonexistent_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "does_not_exist"
        with pytest.raises(CleanupError, match="failed to delete"):
            delete_directory(target)

    def test_raises_without_logging_on_rmtree_error(
        self, tmp_path: Path, capfd
    ) -> None:
        target = tmp_path / "to_delete"
        target.mkdir()
        error_message = "permission denied"

        with mock.patch(
            "rust_cleanup.cleanup.shutil.rmtree", side_effect=OSError(error_message)
        ):
            with pytest.raises(CleanupError, match="failed to delete"):
                delete_directory(target)

        captured = capfd.readouterr()
        assert_equal(
            captured.err, "", "delete_directory should leave stderr logging to callers"
        )

    def test_cleanup_logs_delete_error_from_caller(self, tmp_path: Path, capfd) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()
        error_message = "permission denied"

        with mock.patch(
            "rust_cleanup.cleanup.shutil.rmtree", side_effect=OSError(error_message)
        ):
            scanned, deleted = cleanup_target_dirs(tmp_path, verbose=False)

        captured = capfd.readouterr()
        assert_equal(
            scanned, 1, "cleanup_target_dirs should scan target with delete error"
        )
        assert_equal(deleted, 0, "cleanup_target_dirs should not count failed deletion")
        assert error_message in captured.err, (
            "cleanup_target_dirs should log delete errors to stderr"
        )


class TestFindTargetDirs:
    """Tests for find_target_dirs."""

    def test_finds_target_with_cachedir_tag(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()

        results = find_target_dirs(tmp_path)
        assert_equal(len(results), 1, "find_target_dirs should find one tagged target")
        assert_equal(
            results[0], target, "find_target_dirs should return tagged target path"
        )

    def test_ignores_target_without_cachedir_tag(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()

        results = find_target_dirs(tmp_path)
        assert_equal(len(results), 0, "find_target_dirs should ignore untagged target")

    def test_finds_multiple_targets(self, tmp_path: Path) -> None:
        for i in range(3):
            project = tmp_path / f"project{i}"
            project.mkdir()
            target = project / TARGET_DIR
            target.mkdir()
            (target / CACHEDIR_TAG).touch()

        results = find_target_dirs(tmp_path)
        assert_equal(len(results), 3, "find_target_dirs should find all tagged targets")

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        target = node_modules / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()

        results = find_target_dirs(tmp_path)
        assert_equal(len(results), 0, "find_target_dirs should skip node_modules")

    def test_skips_git_directory(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        target = git_dir / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()

        results = find_target_dirs(tmp_path)
        assert_equal(len(results), 0, "find_target_dirs should skip .git directory")

    def test_does_not_traverse_into_target(self, tmp_path: Path) -> None:
        outer_target = tmp_path / TARGET_DIR
        outer_target.mkdir()
        (outer_target / CACHEDIR_TAG).touch()
        inner_target = outer_target / TARGET_DIR
        inner_target.mkdir()
        (inner_target / CACHEDIR_TAG).touch()

        results = find_target_dirs(tmp_path)
        assert_equal(
            len(results), 1, "find_target_dirs should not traverse nested target dirs"
        )
        assert_equal(
            results[0], outer_target, "find_target_dirs should return outer target"
        )


class TestCleanupTargetDirs:
    """Tests for cleanup_target_dirs."""

    def test_deletes_stale_target(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()
        old_file = target / "old.o"
        old_file.write_text("object code")
        old_time = time.time() - (CUTOFF_SECONDS + 3600)
        os.utime(old_file, (old_time, old_time))

        scanned, deleted = cleanup_target_dirs(tmp_path, verbose=False)
        assert_equal(scanned, 1, "cleanup_target_dirs should scan one target")
        assert_equal(deleted, 1, "cleanup_target_dirs should delete stale target")
        assert not target.exists(), "cleanup_target_dirs should remove stale target"

    def test_keeps_recent_target(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()
        recent_file = target / "recent.o"
        recent_file.write_text("object code")

        scanned, deleted = cleanup_target_dirs(tmp_path, verbose=False)
        assert_equal(scanned, 1, "cleanup_target_dirs should scan recent target")
        assert_equal(deleted, 0, "cleanup_target_dirs should keep recent target")
        assert target.exists(), "cleanup_target_dirs should preserve recent target"

    def test_dry_run_does_not_delete(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()
        old_file = target / "old.o"
        old_file.write_text("object code")
        old_time = time.time() - (CUTOFF_SECONDS + 3600)
        os.utime(old_file, (old_time, old_time))

        scanned, deleted = cleanup_target_dirs(tmp_path, dry_run=True, verbose=False)
        assert_equal(scanned, 1, "cleanup_target_dirs dry run should scan target")
        assert_equal(deleted, 1, "cleanup_target_dirs dry run should count deletion")
        assert target.exists(), "cleanup_target_dirs dry run should preserve target"

    def test_handles_empty_target_directory(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()

        scanned, deleted = cleanup_target_dirs(tmp_path, verbose=False)
        assert_equal(scanned, 1, "cleanup_target_dirs should scan empty target")
        assert_equal(deleted, 1, "cleanup_target_dirs should delete empty target")
        assert not target.exists(), "cleanup_target_dirs should remove empty target"


class TestMain:
    """Tests for main."""

    def test_main_with_valid_path(self, tmp_path: Path) -> None:
        with mock.patch("sys.argv", ["rust_cleanup.py", str(tmp_path)]):
            result = main()
        assert_equal(result, 0, "main should return success for valid path")

    def test_main_with_nonexistent_path(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        with mock.patch("sys.argv", ["rust_cleanup.py", str(nonexistent)]):
            result = main()
        assert_equal(result, 1, "main should return failure for nonexistent path")

    def test_main_with_file_instead_of_directory(self, tmp_path: Path) -> None:
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")
        with mock.patch("sys.argv", ["rust_cleanup.py", str(test_file)]):
            result = main()
        assert_equal(result, 1, "main should return failure for file path")

    def test_main_with_dry_run(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()
        old_file = target / "old.o"
        old_file.write_text("content")
        old_time = time.time() - (CUTOFF_SECONDS + 3600)
        os.utime(old_file, (old_time, old_time))

        with mock.patch("sys.argv", ["rust_cleanup.py", "--dry-run", str(tmp_path)]):
            result = main()
        assert_equal(result, 0, "main should return success for dry run")
        assert target.exists(), "main dry run should preserve target"

    def test_main_default_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = main([])
        assert_equal(result, 0, "main should return success for default path")


class TestIntegration:
    """Integration tests for the complete workflow."""

    def test_full_cleanup_workflow(self, tmp_path: Path) -> None:
        project1 = tmp_path / "project1"
        project1.mkdir()
        target1 = project1 / TARGET_DIR
        target1.mkdir()
        (target1 / CACHEDIR_TAG).touch()
        old_file = target1 / "build.o"
        old_file.write_text("old build")
        old_time = time.time() - (CUTOFF_SECONDS + 3600)
        os.utime(old_file, (old_time, old_time))

        project2 = tmp_path / "project2"
        project2.mkdir()
        target2 = project2 / TARGET_DIR
        target2.mkdir()
        (target2 / CACHEDIR_TAG).touch()
        (target2 / "build.o").write_text("recent build")

        project3 = tmp_path / "project3"
        project3.mkdir()
        target3 = project3 / TARGET_DIR
        target3.mkdir()
        old_file3 = target3 / "build.o"
        old_file3.write_text("old build no tag")
        os.utime(old_file3, (old_time, old_time))

        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        project4 = node_modules / "some-crate"
        project4.mkdir()
        target4 = project4 / TARGET_DIR
        target4.mkdir()
        (target4 / CACHEDIR_TAG).touch()
        old_file4 = target4 / "build.o"
        old_file4.write_text("old build in node_modules")
        os.utime(old_file4, (old_time, old_time))

        scanned, deleted = cleanup_target_dirs(tmp_path, verbose=False)

        assert_equal(
            scanned,
            2,
            "cleanup_target_dirs integration should scan tagged targets only",
        )
        assert_equal(
            deleted,
            1,
            "cleanup_target_dirs integration should delete stale tagged target",
        )
        assert not target1.exists(), (
            "cleanup_target_dirs integration should delete stale target"
        )
        assert target2.exists(), (
            "cleanup_target_dirs integration should preserve recent target"
        )
        assert target3.exists(), (
            "cleanup_target_dirs integration should ignore untagged target"
        )
        assert target4.exists(), (
            "cleanup_target_dirs integration should skip node_modules target"
        )
