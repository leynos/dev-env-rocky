from __future__ import annotations

import json
from pathlib import Path

import pytest

from ansible_collections.agentic.agent_configs.plugins.modules import (
    claude_code_command,
    claude_code_hook,
    claude_code_mcp,
    claude_code_skill,
    codex_cli_hook,
    codex_cli_mcp,
    codex_cli_skill,
    codex_cli_subagent,
    factory_droid_droid,
    factory_droid_hook,
    factory_droid_mcp,
    factory_droid_skill,
)

from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    AnsibleExitJson,
    AnsibleFailJson,
    set_module_args,
)


def run_module(module, args: dict):
    set_module_args(args)
    with pytest.raises(AnsibleExitJson) as exc:
        module.main()
    return exc.value.args[0]


def assert_fails(module, args: dict, message: str) -> None:
    set_module_args(args)
    with pytest.raises(AnsibleFailJson) as exc:
        module.main()
    assert message in exc.value.args[0]["msg"]


@pytest.mark.parametrize(
    ("module", "filename", "extra_args", "expected_frontmatter"),
    [
        (
            claude_code_command,
            "command.md",
            {
                "description": "Run the release checklist.",
                "allowed_tools": ["Bash", "Read"],
                "metadata": {"owner": "release"},
            },
            [
                'name: "Release checklist"',
                'description: "Run the release checklist."',
                "allowed-tools:",
                '  - "Bash"',
                'owner: "release"',
            ],
        ),
        (
            factory_droid_droid,
            "reviewer.md",
            {
                "body": "Review the change.",
                "description": "Review code.",
                "model": "gpt-5.4",
                "reasoning_effort": "high",
                "tools": ["Read", "Grep"],
            },
            [
                'name: "Release checklist"',
                'description: "Review code."',
                'model: "gpt-5.4"',
                'reasoningEffort: "high"',
                "tools:",
            ],
        ),
    ],
)
def test_markdown_file_modules_create_idempotently_and_remove(
    tmp_path: Path,
    module,
    filename: str,
    extra_args: dict,
    expected_frontmatter: list[str],
) -> None:
    path = tmp_path / filename
    args = {
        "name": "Release checklist",
        "path": str(path),
        "body": extra_args.get("body", "Run it."),
        **extra_args,
    }

    result = run_module(module, args)

    assert result["changed"] is True
    assert result["path"] == str(path)
    rendered = path.read_text()
    for expected in expected_frontmatter:
        assert expected in rendered
    assert rendered.endswith((extra_args.get("body", "Run it.") + "\n"))

    assert run_module(module, args)["changed"] is False

    absent = run_module(module, {"name": "Release checklist", "path": str(path), "state": "absent"})

    assert absent["changed"] is True
    assert not path.exists()


@pytest.mark.parametrize(
    ("module", "extra_args", "primary_file", "extra_file"),
    [
        (
            claude_code_skill,
            {
                "description": "Run the release checklist.",
                "allowed_tools": ["Bash"],
                "disable_model_invocation": True,
                "extra_files": {"references/release.md": "Release notes\n"},
            },
            "SKILL.md",
            "references/release.md",
        ),
        (
            factory_droid_skill,
            {
                "description": "Run the release checklist.",
                "user_invocable": True,
                "disable_model_invocation": False,
                "extra_files": {"references/release.md": "Release notes\n"},
            },
            "SKILL.md",
            "references/release.md",
        ),
        (
            codex_cli_skill,
            {
                "description": "Run the release checklist.",
                "openai_yaml": {"tools": ["shell"], "approval": "never"},
                "extra_files": {"references/release.md": "Release notes\n"},
            },
            "SKILL.md",
            "agents/openai.yaml",
        ),
    ],
)
def test_directory_skill_modules_create_extra_files_and_remove(
    tmp_path: Path,
    module,
    extra_args: dict,
    primary_file: str,
    extra_file: str,
) -> None:
    directory = tmp_path / module.__name__.rsplit(".", maxsplit=1)[-1]
    args = {
        "name": "Release checklist",
        "path": str(directory),
        "body": "Run it.",
        **extra_args,
    }

    result = run_module(module, args)

    assert result["changed"] is True
    assert result["directory"] == str(directory)
    assert (directory / primary_file).exists()
    assert (directory / extra_file).exists()

    assert run_module(module, args)["changed"] is False

    absent = run_module(module, {"name": "Release checklist", "path": str(directory), "state": "absent"})

    assert absent["changed"] is True
    assert not directory.exists()


def test_codex_cli_skill_rejects_conflicting_openai_yaml_sources(tmp_path: Path) -> None:
    assert_fails(
        codex_cli_skill,
        {
            "name": "Release checklist",
            "path": str(tmp_path / "skill"),
            "description": "Run it.",
            "openai_yaml": {"tools": ["shell"]},
            "openai_yaml_content": "tools: []\n",
        },
        "mutually exclusive",
    )


def test_markdown_modules_validate_required_present_fields(tmp_path: Path) -> None:
    assert_fails(
        claude_code_command,
        {"name": "Release checklist", "path": str(tmp_path / "command.md")},
        "description is required",
    )
    assert_fails(
        factory_droid_droid,
        {"name": "Reviewer", "path": str(tmp_path / "reviewer.md"), "body": ""},
        "body must be non-empty",
    )


@pytest.mark.parametrize(
    ("module", "args", "root_key", "expected"),
    [
        (
            claude_code_mcp,
            {
                "name": "repo-tools",
                "transport": "stdio",
                "command": "mcp-context-pack",
                "args": ["--stdio"],
                "env": {"LOG": "info"},
            },
            "mcpServers",
            {"command": "mcp-context-pack", "args": ["--stdio"], "env": {"LOG": "info"}},
        ),
        (
            factory_droid_mcp,
            {
                "name": "repo-tools",
                "transport": "http",
                "url": "https://mcp.example.test",
                "headers": {"X-Test": "1"},
                "disabled": True,
                "disabled_tools": ["danger"],
            },
            "mcpServers",
            {
                "type": "http",
                "url": "https://mcp.example.test",
                "headers": {"X-Test": "1"},
                "disabled": True,
                "disabledTools": ["danger"],
            },
        ),
    ],
)
def test_json_mcp_modules_create_idempotently_and_remove(
    tmp_path: Path,
    module,
    args: dict,
    root_key: str,
    expected: dict,
) -> None:
    path = tmp_path / "mcp.json"
    args = {"path": str(path), **args}

    result = run_module(module, args)

    assert result["changed"] is True
    assert result["server"] == expected
    assert json.loads(path.read_text()) == {root_key: {"repo-tools": expected}}

    assert run_module(module, args)["changed"] is False

    absent = run_module(module, {"name": "repo-tools", "path": str(path), "state": "absent"})

    assert absent["changed"] is True
    assert json.loads(path.read_text()) == {}


def test_codex_cli_mcp_writes_toml_and_removes_entry(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    args = {
        "name": "repo-tools",
        "path": str(path),
        "transport": "stdio",
        "command": "mcp-context-pack",
        "args": ["--stdio"],
        "env": {"LOG": "info"},
        "startup_timeout_sec": 20,
    }

    result = run_module(codex_cli_mcp, args)

    assert result["changed"] is True
    assert result["server"]["command"] == "mcp-context-pack"
    rendered = path.read_text()
    assert "[mcp_servers.repo-tools]" in rendered
    assert 'command = "mcp-context-pack"' in rendered
    assert "startup_timeout_sec = 20" in rendered

    assert run_module(codex_cli_mcp, args)["changed"] is False

    absent = run_module(codex_cli_mcp, {"name": "repo-tools", "path": str(path), "state": "absent"})

    assert absent["changed"] is True
    assert path.read_text() == "\n"


@pytest.mark.parametrize(
    ("module", "extra_args", "expected_hook"),
    [
        (
            claude_code_hook,
            {"timeout": 30, "async": True, "shell": "bash", "if_condition": "true"},
            {
                "type": "command",
                "command": "run-checks",
                "timeout": 30,
                "async": True,
                "shell": "bash",
                "if": "true",
            },
        ),
        (
            factory_droid_hook,
            {"extra": {"timeout": 30}},
            {"type": "command", "command": "run-checks", "timeout": 30},
        ),
    ],
)
def test_json_hook_modules_create_idempotently_and_remove(
    tmp_path: Path,
    module,
    extra_args: dict,
    expected_hook: dict,
) -> None:
    path = tmp_path / "settings.json"
    args = {
        "agent_executable": "/bin/sh",
        "path": str(path),
        "event": "Stop",
        "matcher": "Bash",
        "command": "run-checks",
        **extra_args,
    }

    result = run_module(module, args)

    assert result["changed"] is True
    assert result["hook"] == expected_hook
    settings = json.loads(path.read_text())
    assert settings["hooks"]["Stop"][0]["matcher"] == "Bash"
    assert settings["hooks"]["Stop"][0]["hooks"] == [expected_hook]

    assert run_module(module, args)["changed"] is False

    absent = run_module(
        module,
        {
            "agent_executable": "/bin/sh",
            "path": str(path),
            "event": "Stop",
            "matcher": "Bash",
            "command": "run-checks",
            "state": "absent",
        },
    )

    assert absent["changed"] is True
    assert json.loads(path.read_text()) == {}


def test_codex_cli_hook_writes_hook_and_enables_feature_flag(tmp_path: Path) -> None:
    hooks_path = tmp_path / "hooks.json"
    config_path = tmp_path / "config.toml"
    args = {
        "agent_executable": "/bin/sh",
        "path": str(hooks_path),
        "config_path": str(config_path),
        "event": "PostToolUse",
        "matcher": "Bash",
        "command": "run-checks",
        "timeout": 60,
        "status_message": "Checking",
    }

    result = run_module(codex_cli_hook, args)

    assert result["changed"] is True
    assert result["hook"] == {
        "type": "command",
        "command": "run-checks",
        "timeout": 60,
        "async": False,
        "statusMessage": "Checking",
    }
    assert json.loads(hooks_path.read_text())["hooks"]["PostToolUse"][0]["hooks"] == [result["hook"]]
    assert "[features]\ncodex_hooks = true" in config_path.read_text()

    assert run_module(codex_cli_hook, args)["changed"] is False


def test_codex_cli_hook_writes_session_start_hook(tmp_path: Path) -> None:
    hooks_path = tmp_path / "hooks.json"
    config_path = tmp_path / "config.toml"
    args = {
        "agent_executable": "/bin/sh",
        "path": str(hooks_path),
        "config_path": str(config_path),
        "event": "SessionStart",
        "command": "session-start",
        "timeout": 30,
        "async_hook": True,
    }

    result = run_module(codex_cli_hook, args)

    assert result["changed"] is True
    assert result["hook"] == {
        "type": "command",
        "command": "session-start",
        "timeout": 30,
        "async": True,
    }
    assert json.loads(hooks_path.read_text())["hooks"]["SessionStart"][0]["hooks"] == [result["hook"]]
    assert run_module(codex_cli_hook, args)["changed"] is False


def test_codex_cli_hook_check_mode_does_not_write(tmp_path: Path) -> None:
    hooks_path = tmp_path / "hooks.json"
    config_path = tmp_path / "config.toml"

    set_module_args(
        {
            "_ansible_check_mode": True,
            "agent_executable": "/bin/sh",
            "path": str(hooks_path),
            "config_path": str(config_path),
            "event": "PostToolUse",
            "command": "run-checks",
        }
    )
    with pytest.raises(AnsibleExitJson) as exc:
        codex_cli_hook.main()

    result = exc.value.args[0]
    assert result["changed"] is True
    assert not hooks_path.exists()
    assert not config_path.exists()


def test_validate_agent_executable_rejects_missing_path(tmp_path: Path) -> None:
    assert_fails(
        claude_code_hook,
        {
            "agent_executable": str(tmp_path / "missing"),
            "validate_agent_executable": True,
            "path": str(tmp_path / "settings.json"),
            "event": "Stop",
            "command": "run-checks",
        },
        "Executable not found",
    )


def test_codex_cli_subagent_writes_toml_and_removes_entry(tmp_path: Path) -> None:
    path = tmp_path / "reviewer.toml"
    args = {
        "name": "Reviewer",
        "path": str(path),
        "description": "Review changes.",
        "developer_instructions": "Inspect the diff.",
        "nickname_candidates": ["reviewer"],
        "model": "gpt-5.4-mini",
        "model_reasoning_effort": "medium",
        "sandbox_mode": "read-only",
        "mcp_servers": ["context_pack"],
    }

    result = run_module(codex_cli_subagent, args)

    assert result["changed"] is True
    assert result["subagent"]["developer_instructions"] == "Inspect the diff."
    rendered = path.read_text()
    assert 'name = "Reviewer"' in rendered
    assert 'model_reasoning_effort = "medium"' in rendered
    assert 'mcp_servers = ["context_pack"]' in rendered

    assert run_module(codex_cli_subagent, args)["changed"] is False

    absent = run_module(codex_cli_subagent, {"name": "Reviewer", "path": str(path), "state": "absent"})

    assert absent["changed"] is True
    assert not path.exists()


def test_codex_cli_subagent_requires_present_fields(tmp_path: Path) -> None:
    assert_fails(
        codex_cli_subagent,
        {
            "name": "Reviewer",
            "path": str(tmp_path / "reviewer.toml"),
            "description": "Review changes.",
        },
        "developer_instructions is required",
    )
