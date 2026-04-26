"""Clean stale Rust target directories.

This module finds Rust ``target`` directories that are explicitly marked with a
``CACHEDIR.TAG`` file and removes them once they no longer contain recently
modified build artefacts. It is intended for developer machines and automated
sweeps where old Cargo build outputs consume disk space across many worktrees.

Typical command-line usage::

    rust-cleanup ~/src/my-rust-project
    rust-cleanup --dry-run --verbose ~/.lody/repos/example/worktrees/current

The public helpers can also be called directly by tests or maintenance tools::

    from pathlib import Path
    from rust_cleanup.cleanup import cleanup_target_dirs

    scanned, removed = cleanup_target_dirs(Path("~/src/my-rust-project").expanduser())

Important side effects: non-dry-run cleanup deletes stale ``target`` directory
trees with ``shutil.rmtree``. Directories without ``CACHEDIR.TAG`` are ignored,
and directories containing files modified within the freshness window are kept.
"""

import argparse
import collections.abc as cabc
import os
import shutil
import sys
import time
from pathlib import Path


SKIP_DIRS = frozenset(
    {".git", "node_modules", ".svn", ".hg", "__pycache__", ".pytest_cache"}
)
CACHEDIR_TAG = "CACHEDIR.TAG"
TARGET_DIR = "target"
CUTOFF_SECONDS = 24 * 60 * 60


def should_skip_dir(dirname: str) -> bool:
    """Return true when a directory should be skipped during traversal."""
    return dirname in SKIP_DIRS


def has_recent_files(directory: Path, cutoff_time: float) -> bool:
    """Return true when a file in a directory tree is newer than the cutoff.

    Parameters
    ----------
    directory : Path
        Root of the target tree to inspect.
    cutoff_time : float
        POSIX timestamp; files with mtime greater than or equal to this value
        are treated as recent.

    Returns
    -------
    bool
        True if any non-CACHEDIR.TAG file under ``directory`` has mtime greater
        than or equal to ``cutoff_time``, False otherwise.
    """
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
    """Return true when a directory is marked with CACHEDIR.TAG.

    Parameters
    ----------
    directory : Path
        Directory to test.

    Returns
    -------
    bool
        True when a ``CACHEDIR.TAG`` file is present directly inside
        ``directory``.
    """
    return (directory / CACHEDIR_TAG).is_file()


def delete_directory(directory: Path) -> bool:
    """Delete a directory tree.

    Parameters
    ----------
    directory : Path
        Directory tree to remove.

    Returns
    -------
    bool
        True on success.

    Raises
    ------
    CleanupError
        Raised when ``shutil.rmtree`` fails with ``OSError`` or
        ``shutil.Error``. Callers are responsible for stderr logging.
    """
    try:
        shutil.rmtree(directory)
    except (OSError, shutil.Error) as error:
        raise CleanupError(f"failed to delete {directory}: {error}") from error
    return True


def find_target_dirs(root_path: Path) -> list[Path]:
    """Find cache-marked target directories.

    Parameters
    ----------
    root_path : Path
        Directory tree to search.

    Returns
    -------
    list[Path]
        All ``target`` directories under ``root_path`` that contain a
        ``CACHEDIR.TAG`` marker file.

    Notes
    -----
    Nested ``target`` trees inside a matched directory are not descended into.
    """
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


def is_stale(target_path: Path, cutoff_time: float) -> bool:
    """Return true when a target directory has no recent files.

    Parameters
    ----------
    target_path : Path
        Cache-marked ``target`` directory to inspect.
    cutoff_time : float
        POSIX timestamp used as the freshness threshold.

    Returns
    -------
    bool
        True when no non-``CACHEDIR.TAG`` files under ``target_path`` have an
        mtime greater than or equal to ``cutoff_time``.
    """
    return not has_recent_files(target_path, cutoff_time)


def handle_stale_target(target_path: Path, dry_run: bool, verbose: bool) -> int:
    """Handle one stale target directory.

    Parameters
    ----------
    target_path : Path
        Stale cache-marked ``target`` directory to report or remove.
    dry_run : bool
        If True, report the deletion without removing the directory.
    verbose : bool
        If True, print per-directory status messages.

    Returns
    -------
    int
        1 when the directory was removed or would be removed in dry-run mode;
        otherwise 0.
    """
    if dry_run:
        print(f"  Would delete (stale): {target_path}")
        return 1

    if verbose:
        print(f"  Deleting (stale): {target_path}")
    try:
        delete_directory(target_path)
    except CleanupError as error:
        print(f"Error deleting {target_path}: {error}", file=sys.stderr)
        if verbose:
            print(f"  Failed to delete: {target_path}")
        return 0
    else:
        return 1


def cleanup_target_dirs(
    root_path: Path,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> tuple[int, int]:
    """Find and clean up stale target directories below a root path.

    Parameters
    ----------
    root_path : Path
        Root directory to scan.
    dry_run : bool, optional
        If True, report deletions without performing them. Defaults to False.
    verbose : bool, optional
        If True, print per-directory status messages. Defaults to False.

    Returns
    -------
    tuple[int, int]
        ``(scanned, deleted)`` where ``scanned`` is the total number of
        cache-marked target directories found, and ``deleted`` is the number
        actually removed or that would have been removed in dry-run mode.

    Notes
    -----
    Directories containing files newer than the freshness cutoff are preserved.
    """
    current_time = time.time()
    cutoff_time = current_time - CUTOFF_SECONDS

    target_dirs = find_target_dirs(root_path)
    deleted_count = 0

    for target_path in target_dirs:
        if verbose:
            print(f"Scanning: {target_path}")

        if not is_stale(target_path, cutoff_time):
            if verbose:
                print(f"  Keeping (has recent files): {target_path}")
            continue

        deleted_count += handle_stale_target(target_path, dry_run, verbose)

    return len(target_dirs), deleted_count


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Parameters
    ----------
    None
        This function takes no parameters.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser with positional ``path`` argument and ``--dry-run``
        and ``--verbose`` flags.
    """
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


def main(argv: cabc.Sequence[str] | None = None) -> int:
    """Run the rust-cleanup command-line interface.

    Parameters
    ----------
    argv : Sequence[str] | None, optional
        Argument list passed to the parser. If None, ``sys.argv[1:]`` is used.
        Defaults to None.

    Returns
    -------
    int
        0 on success, 1 if the path does not exist or is not a directory.
    """
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


class CleanupError(Exception):
    """Raised when a stale target directory cannot be deleted."""
