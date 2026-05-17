"""Unit tests for rust_cleanup cleanup workflows."""

from __future__ import annotations

import os
import time
from pathlib import Path

from rust_cleanup import (
    CACHEDIR_TAG,
    CUTOFF_SECONDS,
    TARGET_DIR,
    cleanup_target_dirs,
)


def assert_equal(actual: object, expected: object, context: str) -> None:
    assert actual == expected, f"{context}: expected {expected!r}, got {actual!r}"


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
