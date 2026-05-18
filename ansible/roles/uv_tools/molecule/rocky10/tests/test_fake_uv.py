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

    def insert_tool(name: str, version: str) -> None:
        fake_uv._locked_state_update(lambda state: state.update({name: version}))

    threads = [
        threading.Thread(target=insert_tool, args=("ansible", "2.17.0")),
        threading.Thread(target=insert_tool, args=("ruff", "1.0.0")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert fake_uv._read_installed_tools() == {
        "ansible": "2.17.0",
        "ruff": "1.0.0",
    }
