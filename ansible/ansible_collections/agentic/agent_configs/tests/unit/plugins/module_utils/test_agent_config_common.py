"""Test shared agent configuration module utilities.

These unit tests validate TOML and JSON rendering, change tracking, and file
management helpers used by the agent configuration Ansible modules. Run them
with:

    PYTHONPATH=ansible pytest \
        ansible/ansible_collections/agentic/agent_configs/tests/unit/plugins/module_utils/test_agent_config_common.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from ansible_collections.agentic.agent_configs.plugins.module_utils import (
    agent_config_common as common,
)


class ModuleFailure(Exception):
    """Raised when a fake module reports fail_json."""

    pass


@dataclass
class FakeModule:
    """Minimal module object for exercising module utility functions."""

    check_mode: bool = False

    def fail_json(self, **kwargs: Any) -> None:
        """Raise the captured module failure payload."""
        kwargs["failed"] = True
        raise ModuleFailure(kwargs)


@pytest.fixture
def fake_module() -> FakeModule:
    """Return a default fake module for helper tests."""
    return FakeModule()


@pytest.fixture
def settings_path(tmp_path: Path) -> Path:
    """Return a temporary settings JSON path."""
    return tmp_path / "settings.json"


def assert_equal(actual: Any, expected: Any, context: str) -> None:
    """Assert equality with a contextual failure message."""
    assert actual == expected, f"{context}: expected {expected!r}, got {actual!r}"


def assert_is(actual: Any, expected: Any, context: str) -> None:
    """Assert identity with a contextual failure message."""
    assert actual is expected, f"{context}: expected {expected!r}, got {actual!r}"


def test_change_set_tracks_unique_changed_paths_and_details() -> None:
    """ChangeSet should track unique changed paths and latest details."""
    changes = common.ChangeSet()

    changes.note(False, path="/tmp/ignored", ignored=True)
    changes.note(True, path="/tmp/a", reason="created")
    changes.note(True, path="/tmp/a")
    changes.note(True, path="/tmp/b", reason="updated")

    assert changes.changed is True, (
        f"changes.changed expected True, got {changes.changed}"
    )
    assert changes.paths == ["/tmp/a", "/tmp/b"], (
        f"changes.paths expected ['/tmp/a', '/tmp/b'], got {changes.paths}"
    )
    assert changes.details == {"ignored": True, "reason": "updated"}, (
        "changes.details expected {'ignored': True, 'reason': 'updated'}, "
        f"got {changes.details}"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Release checklist", "release-checklist"),
        ("  ../Bad Name!!  ", "bad-name"),
        ("", "resource"),
    ],
)
def test_slugify_normalizes_resource_names(raw: str, expected: str) -> None:
    """slugify should normalise display names into stable resource slugs."""
    assert_equal(
        common.slugify(raw), expected, "common.slugify should normalize resource name"
    )


def test_dump_toml_handles_nested_tables_and_arrays() -> None:
    """dump_toml should render nested tables and array tables."""
    rendered = common.dump_toml(
        {
            "features": {"codex_hooks": True},
            "mcp_servers": {
                "repo-tools": {
                    "command": "mcp-context-pack",
                    "args": ["--stdio"],
                    "env": {"LOG_LEVEL": "info"},
                }
            },
            "profiles": [
                {"name": "fast", "settings": {"timeout": 10}},
                {"name": "slow", "settings": {"timeout": 30}},
            ],
        }
    )

    for expected in (
        "[features]\ncodex_hooks = true",
        "[mcp_servers.repo-tools]",
        'command = "mcp-context-pack"',
        'args = ["--stdio"]',
        "[mcp_servers.repo-tools.env]",
        'LOG_LEVEL = "info"',
        "[[profiles]]",
        "[profiles.settings]",
    ):
        assert expected in rendered, f"common.dump_toml missing {expected!r}"


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_dump_toml_rejects_nan_and_infinity(value: float) -> None:
    """dump_toml should reject floating values unsupported by TOML."""
    with pytest.raises(TypeError, match="TOML does not support NaN or infinity"):
        common.dump_toml({"field": value})


def test_dump_toml_rejects_unsupported_values() -> None:
    """dump_toml should reject unsupported scalar values."""
    with pytest.raises(TypeError, match="Unsupported TOML scalar type"):
        common.dump_toml({"bad": object()})


def test_render_markdown_normalizes_body_and_frontmatter() -> None:
    """render_markdown should normalise frontmatter and body line endings."""
    rendered = common.render_markdown(
        {"name": "Release", "enabled": True, "tools": ["Bash", "Read"]},
        "Body\r\n",
    )

    assert_equal(
        rendered,
        '---\nname: "Release"\nenabled: true\ntools:\n  - "Bash"\n  - "Read"\n---\n\nBody\n',
        "common.render_markdown should normalize frontmatter and body",
    )


def test_manage_named_json_entry_creates_updates_and_removes(
    fake_module: FakeModule,
    settings_path: Path,
) -> None:
    """manage_named_json_entry should create, update, and remove entries."""
    changed, data = common.manage_named_json_entry(
        fake_module,
        str(settings_path),
        root_key="mcpServers",
        name="repo",
        desired={"command": "old"},
        state="present",
    )

    assert_is(changed, True, "manage_named_json_entry should create missing entry")
    assert_equal(
        data,
        {"mcpServers": {"repo": {"command": "old"}}},
        "manage_named_json_entry should return created data",
    )
    assert_equal(
        json.loads(settings_path.read_text()),
        data,
        "manage_named_json_entry should write created data",
    )

    changed, data = common.manage_named_json_entry(
        fake_module,
        str(settings_path),
        root_key="mcpServers",
        name="repo",
        desired={"command": "old"},
        state="present",
    )

    assert_is(changed, False, "manage_named_json_entry should be idempotent")
    assert_equal(
        data,
        {"mcpServers": {"repo": {"command": "old"}}},
        "manage_named_json_entry should keep data unchanged",
    )

    changed, data = common.manage_named_json_entry(
        fake_module,
        str(settings_path),
        root_key="mcpServers",
        name="repo",
        desired=None,
        state="absent",
    )

    assert_is(changed, True, "manage_named_json_entry should remove existing entry")
    assert_equal(
        data, {}, "manage_named_json_entry should return empty data after removal"
    )
    assert_equal(
        json.loads(settings_path.read_text()),
        {},
        "manage_named_json_entry should write removal",
    )


def test_manage_named_json_entry_check_mode_does_not_write(settings_path: Path) -> None:
    """manage_named_json_entry should report check-mode changes without writes."""
    changed, data = common.manage_named_json_entry(
        FakeModule(check_mode=True),
        str(settings_path),
        root_key="mcpServers",
        name="repo",
        desired={"command": "mcp"},
        state="present",
    )

    assert_is(changed, True, "manage_named_json_entry check mode should report change")
    assert_equal(
        data,
        {"mcpServers": {"repo": {"command": "mcp"}}},
        "manage_named_json_entry check mode should return desired data",
    )
    assert not settings_path.exists(), (
        "manage_named_json_entry check mode should not write file"
    )


def test_manage_named_json_entry_rejects_bad_roots(settings_path: Path) -> None:
    """manage_named_json_entry should reject non-object root values."""
    settings_path.write_text(json.dumps({"mcpServers": []}))

    with pytest.raises(ModuleFailure) as exc:
        common.manage_named_json_entry(
            FakeModule(),
            str(settings_path),
            root_key="mcpServers",
            name="repo",
            desired={},
            state="present",
        )

    assert "Expected 'mcpServers' to be a JSON object" in exc.value.args[0]["msg"], (
        "manage_named_json_entry should reject non-object roots"
    )


def test_manage_hook_json_adds_updates_and_removes_hook(
    fake_module: FakeModule,
    settings_path: Path,
) -> None:
    """manage_hook_json should add, update, and remove hook entries."""
    changed, data = common.manage_hook_json(
        fake_module,
        str(settings_path),
        event="Stop",
        matcher="Bash",
        desired_hook={"type": "command", "command": "lint", "timeout": 30},
        state="present",
        identity_keys=("type", "command"),
    )

    assert_is(changed, True, "manage_hook_json should create hook")
    assert_equal(
        data["hooks"]["Stop"][0]["matcher"],
        "Bash",
        "manage_hook_json should set matcher",
    )
    assert_equal(
        data["hooks"]["Stop"][0]["hooks"],
        [{"type": "command", "command": "lint", "timeout": 30}],
        "manage_hook_json should add desired hook",
    )

    changed, data = common.manage_hook_json(
        fake_module,
        str(settings_path),
        event="Stop",
        matcher="Bash",
        desired_hook={"type": "command", "command": "lint", "timeout": 60},
        state="present",
        identity_keys=("type", "command"),
    )

    assert_is(changed, True, "manage_hook_json should update existing hook")
    assert_equal(
        data["hooks"]["Stop"][0]["hooks"][0]["timeout"],
        60,
        "manage_hook_json should update timeout",
    )

    changed, data = common.manage_hook_json(
        fake_module,
        str(settings_path),
        event="Stop",
        matcher="Bash",
        desired_hook={"type": "command", "command": "lint"},
        state="absent",
        identity_keys=("type", "command"),
    )

    assert_is(changed, True, "manage_hook_json should remove existing hook")
    assert_equal(data, {}, "manage_hook_json should prune empty hook roots")


def test_manage_directory_markdown_resource_handles_extra_files_and_absent(
    tmp_path: Path,
) -> None:
    """manage_directory_markdown_resource should manage primary and extra files."""
    module = FakeModule()
    directory = tmp_path / "skill"

    changes = common.manage_directory_markdown_resource(
        module,
        str(directory),
        primary_filename="SKILL.md",
        frontmatter={"name": "Skill"},
        body="Use this skill.",
        state="present",
        extra_files={"references/detail.md": "Details\n"},
    )

    assert_is(
        changes.changed, True, "manage_directory_markdown_resource should report writes"
    )
    assert_equal(
        (directory / "SKILL.md").read_text(),
        '---\nname: "Skill"\n---\n\nUse this skill.\n',
        "manage_directory_markdown_resource should write primary file",
    )
    assert_equal(
        (directory / "references/detail.md").read_text(),
        "Details\n",
        "manage_directory_markdown_resource should write extra file",
    )

    changes = common.manage_directory_markdown_resource(
        module,
        str(directory),
        primary_filename="SKILL.md",
        frontmatter={"name": "Skill"},
        body="Use this skill.",
        state="present",
    )

    assert_is(
        changes.changed,
        False,
        "manage_directory_markdown_resource should be idempotent",
    )

    changes = common.manage_directory_markdown_resource(
        module,
        str(directory),
        primary_filename="SKILL.md",
        frontmatter={},
        body="",
        state="absent",
    )

    assert_is(
        changes.changed,
        True,
        "manage_directory_markdown_resource should remove directory",
    )
    assert not directory.exists(), (
        "manage_directory_markdown_resource should delete directory"
    )


def test_check_mode_directory_resource_reports_without_writing(tmp_path: Path) -> None:
    """Directory resource check mode should report changes without writing."""
    directory = tmp_path / "skill"

    changes = common.manage_directory_markdown_resource(
        FakeModule(check_mode=True),
        str(directory),
        primary_filename="SKILL.md",
        frontmatter={"name": "Skill"},
        body="Use this skill.",
        state="present",
    )

    assert_is(
        changes.changed,
        True,
        "manage_directory_markdown_resource check mode should report change",
    )
    assert not directory.exists(), (
        "manage_directory_markdown_resource check mode should not write"
    )


def test_resolve_scoped_config_path_requires_project_dir_for_project_scope() -> None:
    """Project-scoped config paths should require a project directory."""
    with pytest.raises(ValueError, match="project_dir is required"):
        common.resolve_scoped_config_path(
            path=None,
            scope="project",
            project_dir=None,
            user_path="~/.config/tool.json",
            project_relative_path=".tool/config.json",
        )


def test_maybe_validate_executable_checks_path(tmp_path: Path) -> None:
    """maybe_validate_executable should reject non-executable paths."""
    executable = tmp_path / "tool"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o644)

    with pytest.raises(ModuleFailure) as exc:
        common.maybe_validate_executable(FakeModule(), str(executable), validate=True)

    assert "Path is not executable" in exc.value.args[0]["msg"], (
        "maybe_validate_executable should reject non-executable paths"
    )

    executable.chmod(0o755)
    common.maybe_validate_executable(FakeModule(), str(executable), validate=True)
