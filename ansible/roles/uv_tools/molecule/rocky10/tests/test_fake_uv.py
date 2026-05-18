"""Test the fake uv Molecule fixture state helpers."""

from __future__ import annotations

import importlib.util
import stat
import threading
from pathlib import Path

import pytest


FAKE_UV_PATH = Path(__file__).resolve().parents[1] / "files" / "fake-uv.py"


@pytest.fixture
def fake_uv():
    """Load the fake uv fixture as an importable module."""
    spec = importlib.util.spec_from_file_location("fake_uv", FAKE_UV_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_installed_tools_creates_file_with_restricted_permissions(
    fake_uv,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(fake_uv, "STATE_PATH", state_path)

    fake_uv._write_installed_tools({"ruff": "1.0.0"})

    assert state_path.exists()
    assert fake_uv.json.loads(state_path.read_text(encoding="utf-8")) == {
        "ruff": "1.0.0"
    }
    assert oct(stat.S_IMODE(state_path.stat().st_mode)) == "0o600"


def test_write_installed_tools_is_atomic(
    fake_uv,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    state_path = tmp_path / "state.json"
    recorded_calls = []

    def fake_replace(source, target) -> None:
        recorded_calls.append((source, target))

    monkeypatch.setattr(fake_uv, "STATE_PATH", state_path)
    monkeypatch.setattr(fake_uv.os, "replace", fake_replace)

    fake_uv._write_installed_tools({})

    assert recorded_calls == [(state_path.with_suffix(".tmp"), state_path)]


def test_locked_state_update_mutates_state(
    fake_uv,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(fake_uv, "STATE_PATH", tmp_path / "state.json")

    fake_uv._locked_state_update(lambda state: state.update({"ansible": "2.17.0"}))

    assert fake_uv._read_installed_tools() == {"ansible": "2.17.0"}


def test_locked_state_update_creates_lock_file_with_restricted_permissions(
    fake_uv,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    state_path = tmp_path / "state.json"
    lock_path = state_path.with_suffix(".lock")
    monkeypatch.setattr(fake_uv, "STATE_PATH", state_path)

    fake_uv._locked_state_update(lambda _: None)

    assert lock_path.exists()
    assert oct(stat.S_IMODE(lock_path.stat().st_mode)) == "0o600"


def test_locked_state_update_serialises_concurrent_writes(
    fake_uv,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(fake_uv, "STATE_PATH", tmp_path / "state.json")
    first_has_lock = threading.Event()
    release_first = threading.Event()
    second_attempted_lock = threading.Event()
    attempt_count_lock = threading.Lock()
    lock_attempt_count = 0
    original_flock = fake_uv.fcntl.flock

    def observed_flock(fd, operation) -> None:
        nonlocal lock_attempt_count
        if operation == fake_uv.fcntl.LOCK_EX:
            with attempt_count_lock:
                lock_attempt_count += 1
                if lock_attempt_count == 2:
                    second_attempted_lock.set()
        original_flock(fd, operation)

    monkeypatch.setattr(fake_uv.fcntl, "flock", observed_flock)

    def insert_first_tool() -> None:
        def updater(state) -> None:
            state.update({"ansible": "2.17.0"})
            first_has_lock.set()
            release_first.wait(timeout=5)

        fake_uv._locked_state_update(updater)

    def insert_second_tool() -> None:
        fake_uv._locked_state_update(lambda state: state.update({"ruff": "1.0.0"}))

    first_thread = threading.Thread(target=insert_first_tool)
    second_thread = threading.Thread(target=insert_second_tool)
    first_thread.start()
    assert first_has_lock.wait(timeout=5)

    second_thread.start()
    assert second_attempted_lock.wait(timeout=5)
    release_first.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()

    assert fake_uv._read_installed_tools() == {
        "ansible": "2.17.0",
        "ruff": "1.0.0",
    }
