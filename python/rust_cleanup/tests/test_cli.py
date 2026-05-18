"""Unit tests for rust_cleanup command-line handling."""

import os
import time
import typing as typ
from pathlib import Path
from unittest import mock

from rust_cleanup import CACHEDIR_TAG, CUTOFF_SECONDS, TARGET_DIR, main

if typ.TYPE_CHECKING:
    import pytest


def assert_equal(actual: object, expected: object, context: str) -> None:
    assert actual == expected, f"{context}: expected {expected!r}, got {actual!r}"


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
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = main([])
        assert_equal(result, 0, "main should return success for default path")
