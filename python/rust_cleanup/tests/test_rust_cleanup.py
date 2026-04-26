"""Unit tests for rust_cleanup."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest import mock

from rust_cleanup import (
    CACHEDIR_TAG,
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


class TestShouldSkipDir:
    """Tests for should_skip_dir."""

    def test_skips_git(self) -> None:
        assert should_skip_dir(".git") is True

    def test_skips_node_modules(self) -> None:
        assert should_skip_dir("node_modules") is True

    def test_skips_svn(self) -> None:
        assert should_skip_dir(".svn") is True

    def test_skips_hg(self) -> None:
        assert should_skip_dir(".hg") is True

    def test_skips_pycache(self) -> None:
        assert should_skip_dir("__pycache__") is True

    def test_skips_pytest_cache(self) -> None:
        assert should_skip_dir(".pytest_cache") is True

    def test_does_not_skip_target(self) -> None:
        assert should_skip_dir("target") is False

    def test_does_not_skip_regular_dir(self) -> None:
        assert should_skip_dir("src") is False


class TestIsCacheDir:
    """Tests for is_cache_dir."""

    def test_returns_true_when_cachedir_tag_exists(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / CACHEDIR_TAG).touch()
        assert is_cache_dir(cache_dir) is True

    def test_returns_false_when_cachedir_tag_missing(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        assert is_cache_dir(cache_dir) is False

    def test_returns_false_when_cachedir_tag_is_directory(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / CACHEDIR_TAG).mkdir()
        assert is_cache_dir(cache_dir) is False


class TestHasRecentFiles:
    """Tests for has_recent_files."""

    def test_returns_true_for_recent_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "recent.txt"
        test_file.write_text("content")
        current_time = time.time()
        cutoff_time = current_time - CUTOFF_SECONDS
        assert has_recent_files(tmp_path, cutoff_time) is True

    def test_returns_false_for_old_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "old.txt"
        test_file.write_text("content")
        old_time = time.time() - (CUTOFF_SECONDS + 3600)
        os.utime(test_file, (old_time, old_time))
        cutoff_time = time.time() - CUTOFF_SECONDS
        assert has_recent_files(tmp_path, cutoff_time) is False

    def test_returns_false_for_empty_directory(self, tmp_path: Path) -> None:
        cutoff_time = time.time() - CUTOFF_SECONDS
        assert has_recent_files(tmp_path, cutoff_time) is False

    def test_checks_nested_files(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        test_file = nested / "deep.txt"
        test_file.write_text("content")
        cutoff_time = time.time() - CUTOFF_SECONDS
        assert has_recent_files(tmp_path, cutoff_time) is True

    def test_skips_noisy_directories(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        test_file = git_dir / "recent.txt"
        test_file.write_text("content")
        cutoff_time = time.time() - CUTOFF_SECONDS
        assert has_recent_files(tmp_path, cutoff_time) is False

    def test_handles_missing_file_gracefully(self, tmp_path: Path) -> None:
        test_file = tmp_path / "temp.txt"
        test_file.write_text("content")
        cutoff_time = time.time() - CUTOFF_SECONDS
        test_file.unlink()
        assert has_recent_files(tmp_path, cutoff_time) is False


class TestDeleteDirectory:
    """Tests for delete_directory."""

    def test_deletes_directory_and_contents(self, tmp_path: Path) -> None:
        target = tmp_path / "to_delete"
        target.mkdir()
        (target / "file.txt").write_text("content")
        (target / "subdir").mkdir()
        (target / "subdir" / "another.txt").write_text("more content")

        assert delete_directory(target) is True
        assert not target.exists()

    def test_returns_false_for_nonexistent_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "does_not_exist"
        assert delete_directory(target) is False

    def test_returns_false_and_logs_on_rmtree_error(self, tmp_path: Path, capfd) -> None:
        target = tmp_path / "to_delete"
        target.mkdir()
        error_message = "permission denied"

        with mock.patch("rust_cleanup.cleanup.shutil.rmtree", side_effect=OSError(error_message)):
            assert delete_directory(target) is False

        captured = capfd.readouterr()
        assert error_message in captured.err


class TestFindTargetDirs:
    """Tests for find_target_dirs."""

    def test_finds_target_with_cachedir_tag(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()

        results = find_target_dirs(tmp_path)
        assert len(results) == 1
        assert results[0] == target

    def test_ignores_target_without_cachedir_tag(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()

        results = find_target_dirs(tmp_path)
        assert len(results) == 0

    def test_finds_multiple_targets(self, tmp_path: Path) -> None:
        for i in range(3):
            project = tmp_path / f"project{i}"
            project.mkdir()
            target = project / TARGET_DIR
            target.mkdir()
            (target / CACHEDIR_TAG).touch()

        results = find_target_dirs(tmp_path)
        assert len(results) == 3

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        target = node_modules / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()

        results = find_target_dirs(tmp_path)
        assert len(results) == 0

    def test_skips_git_directory(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        target = git_dir / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()

        results = find_target_dirs(tmp_path)
        assert len(results) == 0

    def test_does_not_traverse_into_target(self, tmp_path: Path) -> None:
        outer_target = tmp_path / TARGET_DIR
        outer_target.mkdir()
        (outer_target / CACHEDIR_TAG).touch()
        inner_target = outer_target / TARGET_DIR
        inner_target.mkdir()
        (inner_target / CACHEDIR_TAG).touch()

        results = find_target_dirs(tmp_path)
        assert len(results) == 1
        assert results[0] == outer_target


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
        assert scanned == 1
        assert deleted == 1
        assert not target.exists()

    def test_keeps_recent_target(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()
        recent_file = target / "recent.o"
        recent_file.write_text("object code")

        scanned, deleted = cleanup_target_dirs(tmp_path, verbose=False)
        assert scanned == 1
        assert deleted == 0
        assert target.exists()

    def test_dry_run_does_not_delete(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()
        old_file = target / "old.o"
        old_file.write_text("object code")
        old_time = time.time() - (CUTOFF_SECONDS + 3600)
        os.utime(old_file, (old_time, old_time))

        scanned, deleted = cleanup_target_dirs(tmp_path, dry_run=True, verbose=False)
        assert scanned == 1
        assert deleted == 1
        assert target.exists()

    def test_handles_empty_target_directory(self, tmp_path: Path) -> None:
        target = tmp_path / TARGET_DIR
        target.mkdir()
        (target / CACHEDIR_TAG).touch()

        scanned, deleted = cleanup_target_dirs(tmp_path, verbose=False)
        assert scanned == 1
        assert deleted == 1
        assert not target.exists()


class TestMain:
    """Tests for main."""

    def test_main_with_valid_path(self, tmp_path: Path) -> None:
        with mock.patch("sys.argv", ["rust_cleanup.py", str(tmp_path)]):
            result = main()
        assert result == 0

    def test_main_with_nonexistent_path(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        with mock.patch("sys.argv", ["rust_cleanup.py", str(nonexistent)]):
            result = main()
        assert result == 1

    def test_main_with_file_instead_of_directory(self, tmp_path: Path) -> None:
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")
        with mock.patch("sys.argv", ["rust_cleanup.py", str(test_file)]):
            result = main()
        assert result == 1

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
        assert result == 0
        assert target.exists()

    def test_main_default_path(self) -> None:
        with mock.patch("sys.argv", ["rust_cleanup.py"]):
            result = main()
        assert result == 0


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

        assert scanned == 2
        assert deleted == 1
        assert not target1.exists()
        assert target2.exists()
        assert target3.exists()
        assert target4.exists()
