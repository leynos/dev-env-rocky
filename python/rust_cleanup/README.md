# rust-cleanup

`rust-cleanup` removes stale Rust `target` directories that contain a
`CACHEDIR.TAG` cache directory tag marker, a file recognized by backup tools as
identifying disposable cache contents. It skips noisy directories such as
`.git`, `node_modules`, `__pycache__`, and `.pytest_cache`, and preserves
target trees that contain files modified within the last 24 hours.

Install it with pip from this directory:

```bash
python -m pip install .
```

Run it against a project or worktree:

```bash
rust-cleanup /path/to/worktree
```

Use `--dry-run` to see what would be removed without deleting anything.
