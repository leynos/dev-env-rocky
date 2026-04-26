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
    pass


@dataclass
class FakeModule:
    check_mode: bool = False

    def fail_json(self, **kwargs: Any) -> None:
        kwargs["failed"] = True
        raise ModuleFailure(kwargs)


def test_change_set_tracks_unique_changed_paths_and_details() -> None:
    changes = common.ChangeSet()

    changes.note(False, path="/tmp/ignored", ignored=True)
    changes.note(True, path="/tmp/a", reason="created")
    changes.note(True, path="/tmp/a")
    changes.note(True, path="/tmp/b", reason="updated")

    assert changes.changed is True
    assert changes.paths == ["/tmp/a", "/tmp/b"]
    assert changes.details == {"ignored": True, "reason": "updated"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Release checklist", "release-checklist"),
        ("  ../Bad Name!!  ", "bad-name"),
        ("", "resource"),
    ],
)
def test_slugify_normalizes_resource_names(raw: str, expected: str) -> None:
    assert common.slugify(raw) == expected


def test_dump_toml_handles_nested_tables_and_arrays() -> None:
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

    assert "[features]\ncodex_hooks = true" in rendered
    assert "[mcp_servers.repo-tools]" in rendered
    assert 'command = "mcp-context-pack"' in rendered
    assert 'args = ["--stdio"]' in rendered
    assert "[mcp_servers.repo-tools.env]" in rendered
    assert 'LOG_LEVEL = "info"' in rendered
    assert "[[profiles]]" in rendered
    assert "[profiles.settings]" in rendered


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_dump_toml_rejects_nan_and_infinity(value: float) -> None:
    with pytest.raises(TypeError, match="TOML does not support NaN or infinity"):
        common.dump_toml({"field": value})


def test_dump_toml_rejects_unsupported_values() -> None:
    with pytest.raises(TypeError, match="Unsupported TOML scalar type"):
        common.dump_toml({"bad": object()})


def test_render_markdown_normalizes_body_and_frontmatter() -> None:
    rendered = common.render_markdown(
        {"name": "Release", "enabled": True, "tools": ["Bash", "Read"]},
        "Body\r\n",
    )

    assert rendered == ('---\nname: "Release"\nenabled: true\ntools:\n  - "Bash"\n  - "Read"\n---\n\nBody\n')


def test_manage_named_json_entry_creates_updates_and_removes(tmp_path: Path) -> None:
    module = FakeModule()
    path = tmp_path / "settings.json"

    changed, data = common.manage_named_json_entry(
        module,
        str(path),
        root_key="mcpServers",
        name="repo",
        desired={"command": "old"},
        state="present",
    )

    assert changed is True
    assert data == {"mcpServers": {"repo": {"command": "old"}}}
    assert json.loads(path.read_text()) == data

    changed, data = common.manage_named_json_entry(
        module,
        str(path),
        root_key="mcpServers",
        name="repo",
        desired={"command": "old"},
        state="present",
    )

    assert changed is False
    assert data == {"mcpServers": {"repo": {"command": "old"}}}

    changed, data = common.manage_named_json_entry(
        module,
        str(path),
        root_key="mcpServers",
        name="repo",
        desired=None,
        state="absent",
    )

    assert changed is True
    assert data == {}
    assert json.loads(path.read_text()) == {}


def test_manage_named_json_entry_check_mode_does_not_write(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"

    changed, data = common.manage_named_json_entry(
        FakeModule(check_mode=True),
        str(path),
        root_key="mcpServers",
        name="repo",
        desired={"command": "mcp"},
        state="present",
    )

    assert changed is True
    assert data == {"mcpServers": {"repo": {"command": "mcp"}}}
    assert not path.exists()


def test_manage_named_json_entry_rejects_bad_roots(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"mcpServers": []}))

    with pytest.raises(ModuleFailure) as exc:
        common.manage_named_json_entry(
            FakeModule(),
            str(path),
            root_key="mcpServers",
            name="repo",
            desired={},
            state="present",
        )

    assert "Expected 'mcpServers' to be a JSON object" in exc.value.args[0]["msg"]


def test_manage_hook_json_adds_updates_and_removes_hook(tmp_path: Path) -> None:
    module = FakeModule()
    path = tmp_path / "settings.json"

    changed, data = common.manage_hook_json(
        module,
        str(path),
        event="Stop",
        matcher="Bash",
        desired_hook={"type": "command", "command": "lint", "timeout": 30},
        state="present",
        identity_keys=("type", "command"),
    )

    assert changed is True
    assert data["hooks"]["Stop"][0]["matcher"] == "Bash"
    assert data["hooks"]["Stop"][0]["hooks"] == [{"type": "command", "command": "lint", "timeout": 30}]

    changed, data = common.manage_hook_json(
        module,
        str(path),
        event="Stop",
        matcher="Bash",
        desired_hook={"type": "command", "command": "lint", "timeout": 60},
        state="present",
        identity_keys=("type", "command"),
    )

    assert changed is True
    assert data["hooks"]["Stop"][0]["hooks"][0]["timeout"] == 60

    changed, data = common.manage_hook_json(
        module,
        str(path),
        event="Stop",
        matcher="Bash",
        desired_hook={"type": "command", "command": "lint"},
        state="absent",
        identity_keys=("type", "command"),
    )

    assert changed is True
    assert data == {}


def test_manage_directory_markdown_resource_handles_extra_files_and_absent(
    tmp_path: Path,
) -> None:
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

    assert changes.changed is True
    assert (directory / "SKILL.md").read_text() == ('---\nname: "Skill"\n---\n\nUse this skill.\n')
    assert (directory / "references/detail.md").read_text() == "Details\n"

    changes = common.manage_directory_markdown_resource(
        module,
        str(directory),
        primary_filename="SKILL.md",
        frontmatter={"name": "Skill"},
        body="Use this skill.",
        state="present",
    )

    assert changes.changed is False

    changes = common.manage_directory_markdown_resource(
        module,
        str(directory),
        primary_filename="SKILL.md",
        frontmatter={},
        body="",
        state="absent",
    )

    assert changes.changed is True
    assert not directory.exists()


def test_check_mode_directory_resource_reports_without_writing(tmp_path: Path) -> None:
    directory = tmp_path / "skill"

    changes = common.manage_directory_markdown_resource(
        FakeModule(check_mode=True),
        str(directory),
        primary_filename="SKILL.md",
        frontmatter={"name": "Skill"},
        body="Use this skill.",
        state="present",
    )

    assert changes.changed is True
    assert not directory.exists()


def test_resolve_scoped_config_path_requires_project_dir_for_project_scope() -> None:
    with pytest.raises(ValueError, match="project_dir is required"):
        common.resolve_scoped_config_path(
            path=None,
            scope="project",
            project_dir=None,
            user_path="~/.config/tool.json",
            project_relative_path=".tool/config.json",
        )


def test_maybe_validate_executable_checks_path(tmp_path: Path) -> None:
    executable = tmp_path / "tool"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o644)

    with pytest.raises(ModuleFailure) as exc:
        common.maybe_validate_executable(FakeModule(), str(executable), validate=True)

    assert "Path is not executable" in exc.value.args[0]["msg"]

    executable.chmod(0o755)
    common.maybe_validate_executable(FakeModule(), str(executable), validate=True)
