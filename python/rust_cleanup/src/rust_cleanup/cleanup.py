"""Clean stale Rust target directories."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Sequence


SKIP_DIRS = frozenset({".git", "node_modules", ".svn", ".hg", "__pycache__", ".pytest_cache"})
CACHEDIR_TAG = "CACHEDIR.TAG"
TARGET_DIR = "target"
CUTOFF_SECONDS = 24 * 60 * 60


def should_skip_dir(dirname: str) -> bool:
    """Return true when a directory should be skipped during traversal."""
    return dirname in SKIP_DIRS


def has_recent_files(directory: Path, cutoff_time: float) -> bool:
    """Return true when a file in a directory tree is newer than the cutoff."""
    for root, dirs, files in os.walk(directory):
        dirs[:] = [dirname for dirname in dirs if not should_skip_dir(dirname)]

        for filename in files:
            if filename == CACHEDIR_TAG:
                continue
            filepath = Path(root) / filename
            try:
                stat = filepath.stat()
            except (OSError, FileNotFoundError):
                continue
            if stat.st_mtime >= cutoff_time:
                return True

    return False


def is_cache_dir(directory: Path) -> bool:
    """Return true when a directory is marked with CACHEDIR.TAG."""
    return (directory / CACHEDIR_TAG).is_file()


def delete_directory(directory: Path) -> bool:
    """Delete a directory tree, returning whether deletion succeeded."""
    try:
        shutil.rmtree(directory)
    except (OSError, shutil.Error) as error:
        print(f"Error deleting {directory}: {error}", file=sys.stderr)
        return False
    return True


def find_target_dirs(root_path: Path) -> list[Path]:
    """Find target directories beneath root_path that are marked as caches."""
    target_dirs: list[Path] = []

    for root, dirs, _files in os.walk(root_path):
        dirs[:] = [dirname for dirname in dirs if not should_skip_dir(dirname)]

        for dirname in dirs[:]:
            if dirname != TARGET_DIR:
                continue

            target_path = Path(root) / dirname
            if is_cache_dir(target_path):
                target_dirs.append(target_path)
                dirs.remove(dirname)

    return target_dirs


def cleanup_target_dirs(
    root_path: Path,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> tuple[int, int]:
    """Find and clean up stale target directories below root_path."""
    current_time = time.time()
    cutoff_time = current_time - CUTOFF_SECONDS

    target_dirs = find_target_dirs(root_path)
    deleted_count = 0

    for target_path in target_dirs:
        if verbose:
            print(f"Scanning: {target_path}")

        has_recent = has_recent_files(target_path, cutoff_time)

        if has_recent:
            if verbose:
                print(f"  Keeping (has recent files): {target_path}")
            continue

        if dry_run:
            print(f"  Would delete (stale): {target_path}")
            deleted_count += 1
            continue

        if verbose:
            print(f"  Deleting (stale): {target_path}")
        if delete_directory(target_path):
            deleted_count += 1
        elif verbose:
            print(f"  Failed to delete: {target_path}")

    return len(target_dirs), deleted_count


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(
        description="Clean up stale Rust target directories.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Root directory to search from (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be deleted without deleting",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed information",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the rust-cleanup command line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    root_path = Path(args.path).resolve()

    if not root_path.exists():
        print(f"Error: Path does not exist: {root_path}", file=sys.stderr)
        return 1

    if not root_path.is_dir():
        print(f"Error: Path is not a directory: {root_path}", file=sys.stderr)
        return 1

    scanned, deleted = cleanup_target_dirs(
        root_path,
        dry_run=args.dry_run,
        verbose=args.verbose or args.dry_run,
    )

    if args.verbose or args.dry_run or deleted > 0:
        action = "Would delete" if args.dry_run else "Deleted"
        print(f"{action} {deleted} of {scanned} target directories")

    return 0


if __name__ == "__main__":
    sys.exit(main())
