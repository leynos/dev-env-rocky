"""Clean stale Rust target directories."""

from rust_cleanup.cleanup import (
    CACHEDIR_TAG,
    CUTOFF_SECONDS,
    SKIP_DIRS,
    TARGET_DIR,
    CleanupError,
    cleanup_target_dirs,
    delete_directory,
    find_target_dirs,
    has_recent_files,
    is_cache_dir,
    main,
    should_skip_dir,
)

__all__ = [
    "CACHEDIR_TAG",
    "CleanupError",
    "CUTOFF_SECONDS",
    "SKIP_DIRS",
    "TARGET_DIR",
    "cleanup_target_dirs",
    "delete_directory",
    "find_target_dirs",
    "has_recent_files",
    "is_cache_dir",
    "main",
    "should_skip_dir",
]
