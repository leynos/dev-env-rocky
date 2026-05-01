"""Test generated agent configuration Ansible modules.

This module verifies that the agent configuration modules render expected
files, report idempotent changes, validate required arguments, and reject
invalid inputs. It is useful when changing module behaviour because the tests
exercise modules through their Ansible-style entrypoints rather than direct
helper calls.

Run these tests from the repository root with the collection on ``PYTHONPATH``::

    PYTHONPATH=ansible pytest ansible/ansible_collections/agentic/agent_configs/tests/unit/plugins/modules/test_agent_config_modules.py
"""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

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
    json_file,
    toml_file,
)
from ansible_collections.agentic.agent_configs.plugins.module_utils import (
    agent_config_common,
)

from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    AnsibleExitJson,
    AnsibleFailJson,
    FakeModule,
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
    actual_message = exc.value.args[0]["msg"]
    assert message in actual_message, (
        f"expected failure message to contain {message!r}, got {actual_message!r}"
    )


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

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    assert result["path"] == str(path), (
        f"expected result['path'] to be {str(path)!r}, got {result['path']!r}"
    )
    rendered = path.read_text()
    for expected in expected_frontmatter:
        assert expected in rendered, (
            f"expected rendered file to contain {expected!r}, got {rendered!r}"
        )
    expected_suffix = extra_args.get("body", "Run it.") + "\n"
    assert rendered.endswith(expected_suffix), (
        f"expected rendered file to end with {expected_suffix!r}, "
        f"got tail {rendered[-len(expected_suffix) - 20 :]!r}"
    )

    rerun_result = run_module(module, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = run_module(
        module, {"name": "Release checklist", "path": str(path), "state": "absent"}
    )

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    assert not path.exists(), f"expected {path} to be removed"


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

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    assert result["directory"] == str(directory), (
        f"expected result['directory'] to be {str(directory)!r}, got {result['directory']!r}"
    )
    assert (directory / primary_file).exists(), (
        f"expected primary file {directory / primary_file} to exist"
    )
    assert (directory / extra_file).exists(), (
        f"expected extra file {directory / extra_file} to exist"
    )

    rerun_result = run_module(module, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = run_module(
        module, {"name": "Release checklist", "path": str(directory), "state": "absent"}
    )

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    assert not directory.exists(), f"expected {directory} to be removed"


def test_codex_cli_skill_rejects_conflicting_openai_yaml_sources(
    tmp_path: Path,
) -> None:
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
            {
                "command": "mcp-context-pack",
                "args": ["--stdio"],
                "env": {"LOG": "info"},
            },
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

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    assert result["server"] == expected, (
        f"expected result['server'] to be {expected!r}, got {result['server']!r}"
    )
    rendered_json = json.loads(path.read_text())
    expected_json = {root_key: {"repo-tools": expected}}
    assert rendered_json == expected_json, (
        f"expected rendered JSON to be {expected_json!r}, got {rendered_json!r}"
    )

    rerun_result = run_module(module, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = run_module(
        module, {"name": "repo-tools", "path": str(path), "state": "absent"}
    )

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    absent_json = json.loads(path.read_text())
    assert absent_json == {}, (
        f"expected rendered JSON to be empty after removal, got {absent_json!r}"
    )


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

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    assert result["server"]["command"] == "mcp-context-pack", (
        f"expected server command to be 'mcp-context-pack', got {result['server']['command']!r}"
    )
    rendered = path.read_text()
    assert "[mcp_servers.repo-tools]" in rendered, (
        "expected rendered TOML to include repo-tools MCP table"
    )
    assert 'command = "mcp-context-pack"' in rendered, (
        "expected rendered TOML to include mcp-context-pack command"
    )
    assert "startup_timeout_sec = 20" in rendered, (
        "expected rendered TOML to include startup timeout"
    )

    rerun_result = run_module(codex_cli_mcp, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = run_module(
        codex_cli_mcp, {"name": "repo-tools", "path": str(path), "state": "absent"}
    )

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    rendered_after_absent = path.read_text()
    assert rendered_after_absent == "\n", (
        f"expected TOML file to contain only a newline, got {rendered_after_absent!r}"
    )


def test_json_file_updates_nested_value_idempotently_and_removes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"hooks": {"Stop": []}}\n')
    args = {
        "path": str(path),
        "key": "env.RUSTC_WRAPPER",
        "value": "/home/leynos/.local/bin/notdeadyet",
    }

    result = run_module(json_file, args)

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    rendered = json.loads(path.read_text())
    assert rendered["env"]["RUSTC_WRAPPER"] == "/home/leynos/.local/bin/notdeadyet", (
        f"expected JSON env value to be written, got {rendered!r}"
    )
    assert rendered["hooks"] == {"Stop": []}, (
        f"expected existing settings to be preserved, got {rendered!r}"
    )

    rerun_result = run_module(json_file, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = run_module(
        json_file, {"path": str(path), "key": "env.RUSTC_WRAPPER", "state": "absent"}
    )

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    rendered_after_absent = json.loads(path.read_text())
    assert "RUSTC_WRAPPER" not in rendered_after_absent["env"], (
        f"expected JSON env value to be removed, got {rendered_after_absent!r}"
    )


def test_toml_file_updates_nested_value_idempotently_and_removes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[features]\ncodex_hooks = true\n\n[env]\nSCCACHE_DIR = "/old"\n')
    args = {
        "path": str(path),
        "key": "env.SCCACHE_DIR",
        "value": "/home/leynos/.cache/sccache",
    }

    result = run_module(toml_file, args)

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    rendered = path.read_text()
    assert "[features]" in rendered, (
        f"expected existing TOML tables to be preserved, got {rendered!r}"
    )
    assert "codex_hooks = true" in rendered, (
        f"expected existing TOML values to be preserved, got {rendered!r}"
    )
    assert 'SCCACHE_DIR = "/home/leynos/.cache/sccache"' in rendered, (
        f"expected TOML env value to be written, got {rendered!r}"
    )

    rerun_result = run_module(toml_file, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = run_module(
        toml_file, {"path": str(path), "key": "env.SCCACHE_DIR", "state": "absent"}
    )

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    assert "SCCACHE_DIR" not in path.read_text(), (
        f"expected TOML env value to be removed, got {path.read_text()!r}"
    )


def test_sccache_environment_modules_write_expected_structures(tmp_path: Path) -> None:
    expected_env = {
        "RUSTC_WRAPPER": "/home/leynos/.local/bin/notdeadyet",
        "RUSTC_HEARTBEAT_SECS": "45",
        "SCCACHE_DIR": "/home/leynos/.cache/sccache",
        "SCCACHE_CACHE_SIZE": "120G",
    }
    codex_path = tmp_path / "config.toml"
    claude_path = tmp_path / "settings.json"

    for key, value in expected_env.items():
        run_module(
            toml_file,
            {"path": str(codex_path), "key": f"env.{key}", "value": value},
        )
        run_module(
            json_file,
            {"path": str(claude_path), "key": f"env.{key}", "value": value},
        )

    codex = tomllib.loads(codex_path.read_text())
    claude = json.loads(claude_path.read_text())
    assert codex == {"env": expected_env}, (
        f"expected Codex TOML env table to match sccache settings, got {codex!r}"
    )
    assert claude == {"env": expected_env}, (
        f"expected Claude JSON env object to match sccache settings, got {claude!r}"
    )


def test_resolve_relative_config_file_returns_path_relative_to_config_dir(
    tmp_path: Path,
) -> None:
    subagent_path = tmp_path / ".codex" / "agents" / "reviewer.toml"
    config_path = tmp_path / ".codex" / "config.toml"

    result = agent_config_common.resolve_relative_config_file(
        str(subagent_path), str(config_path)
    )

    assert result == "agents/reviewer.toml"


def test_resolve_relative_config_file_returns_absolute_path_outside_config_dir(
    tmp_path: Path,
) -> None:
    subagent_path = tmp_path / "shared" / "reviewer.toml"
    config_path = tmp_path / ".codex" / "config.toml"

    result = agent_config_common.resolve_relative_config_file(
        str(subagent_path), str(config_path)
    )

    assert result == str(subagent_path)


@pytest.mark.parametrize("module", [json_file, toml_file])
def test_structured_file_modules_require_value_when_present(
    tmp_path: Path, module
) -> None:
    assert_fails(
        module,
        {"path": str(tmp_path / "config"), "key": "env.RUSTC_WRAPPER"},
        "value is required",
    )


@pytest.mark.parametrize("module", [json_file, toml_file])
def test_structured_file_modules_reject_non_octal_modes(tmp_path: Path, module) -> None:
    path = tmp_path / "config"

    assert_fails(
        module,
        {
            "path": str(path),
            "key": "env.RUSTC_WRAPPER",
            "value": "/home/leynos/.local/bin/notdeadyet",
            "mode": "u=rw",
        },
        "mode must be an octal string",
    )
    assert not path.exists(), "expected invalid mode to fail before writing the file"


def test_json_file_reports_write_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_write(path: str, content: str) -> None:
        raise OSError("disk denied")

    monkeypatch.setattr(json_file, "atomic_write_text", fail_write)
    assert_fails(
        json_file,
        {
            "path": str(tmp_path / "settings.json"),
            "key": "env.RUSTC_WRAPPER",
            "value": "/home/leynos/.local/bin/notdeadyet",
        },
        "Failed to write JSON file",
    )


def test_toml_file_reports_write_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_write(path: str, content: str) -> None:
        raise OSError("disk denied")

    monkeypatch.setattr(toml_file, "atomic_write_text", fail_write)
    assert_fails(
        toml_file,
        {
            "path": str(tmp_path / "config.toml"),
            "key": "env.SCCACHE_DIR",
            "value": "/home/leynos/.cache/sccache",
        },
        "Failed to write TOML file",
    )


def test_toml_file_reports_parse_errors(tmp_path: Path) -> None:
    class DummyModule:
        def fail_json(self, **kwargs):
            raise AnsibleFailJson(kwargs)

    path = tmp_path / "config.toml"
    path.write_text("[env\n")
    tomlkit, parse_error = toml_file.import_tomlkit(DummyModule())

    with pytest.raises(AnsibleFailJson) as exc:
        toml_file.load_document(DummyModule(), tomlkit, parse_error, str(path))

    actual_message = exc.value.args[0]["msg"]
    assert "Failed to parse TOML file" in actual_message


def test_toml_file_does_not_mask_unexpected_parse_errors(tmp_path: Path) -> None:
    class DummyModule:
        def fail_json(self, **kwargs):
            raise AnsibleFailJson(kwargs)

    class BrokenTomlkit:
        @staticmethod
        def document():
            return {}

        @staticmethod
        def parse(content: str):
            raise RuntimeError("unexpected parser failure")

    path = tmp_path / "config.toml"
    path.write_text("[env]\n")
    _, parse_error = toml_file.import_tomlkit(DummyModule())

    with pytest.raises(RuntimeError, match="unexpected parser failure"):
        toml_file.load_document(DummyModule(), BrokenTomlkit, parse_error, str(path))


@pytest.mark.parametrize(
    ("module", "message"),
    [
        (json_file, "Failed to chmod JSON file"),
        (toml_file, "Failed to chmod TOML file"),
    ],
)
def test_structured_file_modules_report_chmod_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module,
    message: str,
) -> None:
    path = tmp_path / "config"
    path.write_text("{}\n" if module is json_file else "\n")

    def fail_chmod(path: str, mode: int) -> None:
        raise OSError("chmod denied")

    monkeypatch.setattr(module.os, "chmod", fail_chmod)
    assert_fails(
        module,
        {
            "path": str(path),
            "key": "env.RUSTC_WRAPPER",
            "value": "/home/leynos/.local/bin/notdeadyet",
            "mode": "0644",
        },
        message,
    )


@pytest.mark.parametrize("module", [json_file, toml_file])
def test_structured_file_modules_compare_special_permission_bits(
    tmp_path: Path, module
) -> None:
    path = tmp_path / "config"
    path.write_text("{}\n" if module is json_file else "\n")
    path.chmod(0o1777)

    changed = module.enforce_mode(FakeModule(), str(path), 0o1777)

    assert changed is False


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

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    assert result["hook"] == expected_hook, (
        f"expected result['hook'] to be {expected_hook!r}, got {result['hook']!r}"
    )
    settings = json.loads(path.read_text())
    assert settings["hooks"]["Stop"][0]["matcher"] == "Bash", (
        f"expected Stop hook matcher to be 'Bash', got {settings['hooks']['Stop'][0]['matcher']!r}"
    )
    assert settings["hooks"]["Stop"][0]["hooks"] == [expected_hook], (
        f"expected Stop hooks to be {[expected_hook]!r}, got {settings['hooks']['Stop'][0]['hooks']!r}"
    )

    rerun_result = run_module(module, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

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

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    absent_settings = json.loads(path.read_text())
    assert absent_settings == {}, (
        f"expected settings JSON to be empty after removal, got {absent_settings!r}"
    )


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

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    expected_hook = {
        "type": "command",
        "command": "run-checks",
        "timeout": 60,
        "async": False,
        "statusMessage": "Checking",
    }
    assert result["hook"] == expected_hook, (
        f"expected result['hook'] to be {expected_hook!r}, got {result['hook']!r}"
    )
    rendered_hooks = json.loads(hooks_path.read_text())
    assert rendered_hooks["hooks"]["PostToolUse"][0]["hooks"] == [result["hook"]], (
        f"expected PostToolUse hooks to be {[result['hook']]!r}, "
        f"got {rendered_hooks['hooks']['PostToolUse'][0]['hooks']!r}"
    )
    rendered_config = config_path.read_text()
    assert "[features]\ncodex_hooks = true" in rendered_config, (
        f"expected Codex hook feature flag in config, got {rendered_config!r}"
    )

    rerun_result = run_module(codex_cli_hook, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )


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

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    expected_hook = {
        "type": "command",
        "command": "session-start",
        "timeout": 30,
        "async": True,
    }
    assert result["hook"] == expected_hook, (
        f"expected result['hook'] to be {expected_hook!r}, got {result['hook']!r}"
    )
    rendered_hooks = json.loads(hooks_path.read_text())
    assert rendered_hooks["hooks"]["SessionStart"][0]["hooks"] == [result["hook"]], (
        f"expected SessionStart hooks to be {[result['hook']]!r}, "
        f"got {rendered_hooks['hooks']['SessionStart'][0]['hooks']!r}"
    )
    rerun_result = run_module(codex_cli_hook, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )


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
    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    assert not hooks_path.exists(), f"expected check mode not to create {hooks_path}"
    assert not config_path.exists(), f"expected check mode not to create {config_path}"


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
    config_path = tmp_path / "config.toml"
    path = tmp_path / "agents/reviewer.toml"
    args = {
        "name": "Reviewer",
        "path": str(path),
        "config_path": str(config_path),
        "description": "Review changes.",
        "developer_instructions": "Inspect the diff.",
        "nickname_candidates": ["reviewer"],
        "model": "gpt-5.4-mini",
        "model_reasoning_effort": "medium",
        "sandbox_mode": "read-only",
        "mcp_servers": ["context_pack"],
    }

    result = run_module(codex_cli_subagent, args)

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    assert result["subagent"]["developer_instructions"] == "Inspect the diff.", (
        "expected developer instructions to be 'Inspect the diff.', "
        f"got {result['subagent']['developer_instructions']!r}"
    )
    rendered = path.read_text()
    assert 'name = "Reviewer"' in rendered, (
        "expected rendered TOML to include subagent name"
    )
    assert 'model_reasoning_effort = "medium"' in rendered, (
        "expected rendered TOML to include reasoning effort"
    )
    assert 'mcp_servers = ["context_pack"]' in rendered, (
        "expected rendered TOML to include MCP servers"
    )
    rendered_config = config_path.read_text()
    assert "[agents.reviewer]" in rendered_config, (
        "expected rendered config to include reviewer agent registry"
    )
    assert 'description = "Review changes."' in rendered_config, (
        "expected rendered config to include agent description"
    )
    assert 'config_file = "agents/reviewer.toml"' in rendered_config, (
        "expected rendered config to include subagent config file"
    )
    assert 'nickname_candidates = ["reviewer"]' in rendered_config, (
        "expected rendered config to include nickname candidates"
    )

    rerun_result = run_module(codex_cli_subagent, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = run_module(
        codex_cli_subagent,
        {
            "name": "Reviewer",
            "path": str(path),
            "config_path": str(config_path),
            "state": "absent",
        },
    )

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    assert not path.exists(), f"expected {path} to be removed"
    rendered_config_after_absent = config_path.read_text()
    assert rendered_config_after_absent == "\n", (
        f"expected config TOML file to contain only a newline, got {rendered_config_after_absent!r}"
    )


def test_codex_cli_subagent_rolls_back_file_when_registry_update_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.toml"
    path = tmp_path / "agents/reviewer.toml"

    def fail_registry(*args, **kwargs):
        raise AnsibleFailJson({"msg": "registry denied"})

    monkeypatch.setattr(codex_cli_subagent, "manage_named_toml_entry", fail_registry)
    assert_fails(
        codex_cli_subagent,
        {
            "name": "Reviewer",
            "path": str(path),
            "config_path": str(config_path),
            "description": "Review changes.",
            "developer_instructions": "Inspect the diff.",
        },
        "Failed to register Codex subagent reviewer",
    )
    assert not path.exists(), "expected subagent file to be rolled back"
    assert not config_path.exists(), "expected config file to remain absent"


def test_codex_cli_subagent_reraises_unexpected_registry_update_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.toml"
    path = tmp_path / "agents/reviewer.toml"

    def fail_registry(*args, **kwargs):
        raise RuntimeError("unexpected registry failure")

    monkeypatch.setattr(codex_cli_subagent, "manage_named_toml_entry", fail_registry)
    set_module_args(
        {
            "name": "Reviewer",
            "path": str(path),
            "config_path": str(config_path),
            "description": "Review changes.",
            "developer_instructions": "Inspect the diff.",
        }
    )

    with pytest.raises(RuntimeError, match="unexpected registry failure"):
        codex_cli_subagent.main()


def test_codex_cli_subagent_reraises_unexpected_registry_removal_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.toml"
    path = tmp_path / "agents/reviewer.toml"

    def fail_registry(*args, **kwargs):
        raise RuntimeError("unexpected registry failure")

    monkeypatch.setattr(codex_cli_subagent, "manage_named_toml_entry", fail_registry)
    set_module_args(
        {
            "name": "Reviewer",
            "path": str(path),
            "config_path": str(config_path),
            "state": "absent",
        }
    )

    with pytest.raises(RuntimeError, match="unexpected registry failure"):
        codex_cli_subagent.main()


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
