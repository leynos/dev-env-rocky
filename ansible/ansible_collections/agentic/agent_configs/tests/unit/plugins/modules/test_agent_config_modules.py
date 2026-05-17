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
from typing import NoReturn

import pytest
import tomllib
from ansible_collections.agentic.agent_configs.plugins.module_utils import (
    agent_config_common,
)
from ansible_collections.agentic.agent_configs.plugins.modules import (
    claude_code_command,
    claude_code_hook,
    claude_code_mcp,
    claude_code_skill,
    codex_cli_hook,
    codex_cli_mcp,
    codex_cli_skill,
    codex_cli_subagent,
    cursor_cli_mcp,
    cursor_cli_skill,
    deepseek_tui_hook,
    deepseek_tui_mcp,
    deepseek_tui_skill,
    factory_droid_droid,
    factory_droid_hook,
    factory_droid_mcp,
    factory_droid_model,
    factory_droid_skill,
    json_file,
    toml_file,
)
from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    AnsibleExitJson,
    AnsibleFailJson,
    FakeModule,
    assert_module_fails,
    run_module,
    set_module_args,
)


def _run_module(module, args: dict) -> dict:
    return run_module(module, args)


def _assert_fails(module, args: dict, message: str) -> None:
    return assert_module_fails(module, args, message)


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
    """Verify markdown-file modules create a file, rerun idempotently, and remove it."""
    path = tmp_path / filename
    args = {
        "name": "Release checklist",
        "path": str(path),
        "body": extra_args.get("body", "Run it."),
        **extra_args,
    }

    result = _run_module(module, args)

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

    rerun_result = _run_module(module, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = _run_module(
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
        (
            cursor_cli_skill,
            {
                "description": "Run the release checklist.",
                "metadata": {"owner": "release"},
                "extra_files": {"references/release.md": "Release notes\n"},
            },
            "SKILL.md",
            "references/release.md",
        ),
        (
            deepseek_tui_skill,
            {
                "description": "Run the release checklist.",
                "metadata": {"owner": "release"},
                "extra_files": {"references/release.md": "Release notes\n"},
            },
            "SKILL.md",
            "references/release.md",
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
    """Verify directory skill modules write auxiliary files and remove them on absent."""
    directory = tmp_path / module.__name__.rsplit(".", maxsplit=1)[-1]
    args = {
        "name": "Release checklist",
        "path": str(directory),
        "body": "Run it.",
        **extra_args,
    }

    result = _run_module(module, args)

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

    rerun_result = _run_module(module, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = _run_module(
        module, {"name": "Release checklist", "path": str(directory), "state": "absent"}
    )

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    assert not directory.exists(), f"expected {directory} to be removed"


def test_codex_cli_skill_rejects_conflicting_openai_yaml_sources(
    tmp_path: Path,
) -> None:
    _assert_fails(
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
    """Verify markdown-file modules reject state=present without required fields."""
    _assert_fails(
        claude_code_command,
        {"name": "Release checklist", "path": str(tmp_path / "command.md")},
        "description is required",
    )
    _assert_fails(
        factory_droid_droid,
        {"name": "Reviewer", "path": str(tmp_path / "reviewer.md"), "body": ""},
        "body must be non-empty",
    )


@pytest.mark.parametrize(
    ("module", "args", "root_key", "expected", "expected_file"),
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
            None,
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
            None,
        ),
        (
            cursor_cli_mcp,
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
                "env": "REDACTED",
            },
            {
                "command": "mcp-context-pack",
                "args": ["--stdio"],
                "env": {"LOG": "info"},
            },
        ),
        (
            deepseek_tui_mcp,
            {
                "name": "repo-tools",
                "transport": "stdio",
                "command": "mcp-context-pack",
                "args": ["--stdio"],
                "env": {"LOG": "info"},
                "required": True,
                "enabled_tools": ["status"],
                "disabled_tools": ["danger"],
            },
            "servers",
            {
                "command": "mcp-context-pack",
                "args": ["--stdio"],
                "env": {"LOG": "info"},
                "required": True,
                "enabled_tools": ["status"],
                "disabled_tools": ["danger"],
            },
            None,
        ),
    ],
)
def test_json_mcp_modules_create_idempotently_and_remove(
    tmp_path: Path,
    module,
    args: dict,
    root_key: str,
    expected: dict,
    expected_file: dict | None,
) -> None:
    """Verify JSON-MCP modules create an entry, rerun idempotently, and remove it."""
    path = tmp_path / "mcp.json"
    args = {"path": str(path), **args}

    result = _run_module(module, args)

    assert result["changed"] is True, (
        f"expected result['changed'] to be True, got {result['changed']!r}"
    )
    assert result["server"] == expected, (
        f"expected result['server'] to be {expected!r}, got {result['server']!r}"
    )
    stored = expected_file if expected_file is not None else expected
    rendered_json = json.loads(path.read_text())
    expected_json = {root_key: {"repo-tools": stored}}
    assert rendered_json == expected_json, (
        f"expected rendered JSON to be {expected_json!r}, got {rendered_json!r}"
    )

    rerun_result = _run_module(module, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = _run_module(
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

    result = _run_module(codex_cli_mcp, args)

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

    rerun_result = _run_module(codex_cli_mcp, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = _run_module(
        codex_cli_mcp, {"name": "repo-tools", "path": str(path), "state": "absent"}
    )

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    rendered_after_absent = path.read_text()
    assert rendered_after_absent == "\n", (
        f"expected TOML file to contain only a newline, got {rendered_after_absent!r}"
    )


@pytest.mark.parametrize(
    ("module", "config_dir", "root_key", "url", "expected_server"),
    [
        (
            cursor_cli_mcp,
            ".cursor",
            "mcpServers",
            "https://mcp.example.test",
            {"type": "http", "url": "https://mcp.example.test", "headers": {}},
        ),
        (
            deepseek_tui_mcp,
            ".deepseek",
            "servers",
            "http://localhost:3000/mcp",
            {"url": "http://localhost:3000/mcp"},
        ),
    ],
)
def test_mcp_module_resolves_project_scoped_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module,
    config_dir: str,
    root_key: str,
    url: str,
    expected_server: dict,
) -> None:
    """Verify MCP modules resolve project-scoped config paths and write correct JSON."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    result = _run_module(
        module,
        {
            "name": "repo-tools",
            "scope": "project",
            "project_dir": str(project_dir),
            "transport": "http",
            "url": url,
        },
    )

    assert result["path"] == str(project_dir / config_dir / "mcp.json")
    rendered = json.loads((project_dir / config_dir / "mcp.json").read_text())
    assert rendered == {root_key: {"repo-tools": expected_server}}

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    user_result = _run_module(
        module,
        {
            "name": "repo-tools",
            "scope": "user",
            "transport": "http",
            "url": url,
        },
    )

    expected_user_path = home / config_dir / "mcp.json"
    assert user_result["path"] == str(expected_user_path)
    rendered_user = json.loads(expected_user_path.read_text())
    assert rendered_user == {root_key: {"repo-tools": expected_server}}


def test_factory_droid_model_manages_custom_model_list(tmp_path: Path) -> None:
    """Verify Factory Droid custom model entries are keyed by model id."""
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "theme": "dark",
                "customModels": [
                    {
                        "model": "existing-model",
                        "displayName": "Existing",
                        "provider": "anthropic",
                    }
                ],
            }
        )
        + "\n"
    )
    args = {
        "path": str(path),
        "model": "deepseek-v4-pro",
        "display_name": "DeepSeek V4 Pro",
        "provider": "anthropic",
        "base_url": "https://api.deepseek.com/anthropic",
        "api_key": "secret-token",
        "max_output_tokens": 8192,
        "extra": {"noImageSupport": True},
    }

    result = _run_module(factory_droid_model, args)

    expected_stored_model = {
        "model": "deepseek-v4-pro",
        "displayName": "DeepSeek V4 Pro",
        "baseUrl": "https://api.deepseek.com/anthropic",
        "apiKey": "secret-token",
        "provider": "anthropic",
        "maxOutputTokens": 8192,
        "noImageSupport": True,
    }
    assert result["changed"] is True
    assert result["custom_model"]["apiKey"] == "REDACTED", (
        f"expected apiKey in result to be 'REDACTED', got {result['custom_model']['apiKey']!r}"
    )
    assert "secret-token" not in result["custom_model"].values(), (
        "expected raw API key value to be absent from result['custom_model']"
    )
    assert result["custom_model"]["model"] == "deepseek-v4-pro"
    assert result["custom_model"]["displayName"] == "DeepSeek V4 Pro"
    rendered = json.loads(path.read_text())
    assert rendered["theme"] == "dark"
    assert rendered["customModels"] == [
        {
            "model": "existing-model",
            "displayName": "Existing",
            "provider": "anthropic",
        },
        expected_stored_model,
    ]

    rerun_result = _run_module(factory_droid_model, args)
    assert rerun_result["changed"] is False

    updated = _run_module(
        factory_droid_model,
        {
            **args,
            "display_name": "DeepSeek V4 Pro Updated",
            "max_output_tokens": 16384,
        },
    )
    assert updated["changed"] is True
    assert updated["custom_model"]["displayName"] == "DeepSeek V4 Pro Updated"
    assert updated["custom_model"]["maxOutputTokens"] == 16384

    absent = _run_module(
        factory_droid_model,
        {"path": str(path), "model": "deepseek-v4-pro", "state": "absent"},
    )
    assert absent["changed"] is True
    absent_json = json.loads(path.read_text())
    assert absent_json == {
        "theme": "dark",
        "customModels": [
            {
                "model": "existing-model",
                "displayName": "Existing",
                "provider": "anthropic",
            }
        ],
    }


def test_json_file_updates_nested_value_idempotently_and_removes(
    tmp_path: Path,
) -> None:
    """Verify json_file writes a nested value, reruns idempotently, and removes it."""
    path = tmp_path / "settings.json"
    path.write_text('{"hooks": {"Stop": []}}\n')
    args = {
        "path": str(path),
        "key": "env.RUSTC_WRAPPER",
        "value": "/home/leynos/.local/bin/notdeadyet",
    }

    result = _run_module(json_file, args)

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

    rerun_result = _run_module(json_file, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = _run_module(
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
    """Verify toml_file writes a nested value, reruns idempotently, and removes it."""
    path = tmp_path / "config.toml"
    path.write_text('[features]\ncodex_hooks = true\n\n[env]\nSCCACHE_DIR = "/old"\n')
    args = {
        "path": str(path),
        "key": "env.SCCACHE_DIR",
        "value": "/home/leynos/.cache/sccache",
    }

    result = _run_module(toml_file, args)

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

    rerun_result = _run_module(toml_file, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = _run_module(
        toml_file, {"path": str(path), "key": "env.SCCACHE_DIR", "state": "absent"}
    )

    assert absent["changed"] is True, (
        f"expected absent result['changed'] to be True, got {absent['changed']!r}"
    )
    assert "SCCACHE_DIR" not in path.read_text(), (
        f"expected TOML env value to be removed, got {path.read_text()!r}"
    )


def test_json_file_mode_idempotency(tmp_path: Path) -> None:
    """Applying the same mode twice must report changed=False on the second run."""
    for mode_str in ("0644", "1777", "4755"):
        target = str(tmp_path / f"cfg_{mode_str}.json")
        args = {
            "path": target,
            "key": "x",
            "value": 1,
            "state": "present",
            "mode": mode_str,
        }

        first = _run_module(json_file, args)
        assert first["changed"] is True, (
            f"mode {mode_str}: expected changed=True on first run"
        )
        second = _run_module(json_file, args)
        assert second["changed"] is False, (
            f"mode {mode_str}: expected idempotent mode rerun to report "
            f"changed=False, got {second['changed']!r}"
        )


def test_toml_file_mode_idempotency(tmp_path: Path) -> None:
    """Applying the same mode twice must report changed=False on the second run."""
    for mode_str in ("0644", "1777", "4755"):
        target = str(tmp_path / f"cfg_{mode_str}.toml")
        args = {
            "path": target,
            "key": "x",
            "value": 1,
            "state": "present",
            "mode": mode_str,
        }

        first = _run_module(toml_file, args)
        assert first["changed"] is True, (
            f"mode {mode_str}: expected changed=True on first run"
        )
        second = _run_module(toml_file, args)
        assert second["changed"] is False, (
            f"mode {mode_str}: expected idempotent mode rerun to report "
            f"changed=False, got {second['changed']!r}"
        )


def test_toml_file_removes_legacy_sccache_block_before_writing(
    tmp_path: Path,
) -> None:
    """Verify toml_file repairs the obsolete sccache block that duplicated [env]."""
    path = tmp_path / "config.toml"
    path.write_text(
        '[env]\nPATH = "/usr/bin"\n\n'
        "# BEGIN ANSIBLE MANAGED BLOCK - sccache env\n"
        "[env]\n"
        'SCCACHE_DIR = "/old/cache"\n'
        "# END ANSIBLE MANAGED BLOCK - sccache env\n"
    )

    result = _run_module(
        toml_file,
        {
            "path": str(path),
            "key": "env.SCCACHE_DIR",
            "value": "/home/leynos/.cache/sccache",
        },
    )

    rendered = path.read_text()
    parsed = tomllib.loads(rendered)
    assert result["changed"] is True
    assert "# BEGIN ANSIBLE MANAGED BLOCK - sccache env" not in rendered
    assert rendered.count("[env]") == 1
    assert parsed["env"]["PATH"] == "/usr/bin"
    assert parsed["env"]["SCCACHE_DIR"] == "/home/leynos/.cache/sccache"


def test_toml_file_absent_with_missing_parent_reports_no_change(
    tmp_path: Path,
) -> None:
    """Verify state=absent does not create empty tables when the parent is absent."""
    path = tmp_path / "config.toml"
    path.write_text("[features]\ncodex_hooks = true\n")

    result = _run_module(
        toml_file,
        {"path": str(path), "key": "env.SCCACHE_DIR", "state": "absent"},
    )

    assert result["changed"] is False, (
        f"expected changed=False when parent table is absent, got {result['changed']!r}"
    )
    rendered = path.read_text()
    parsed = tomllib.loads(rendered)
    assert "env" not in parsed, (
        f"expected no spurious [env] table in output, got {rendered!r}"
    )


def test_toml_file_absent_with_legacy_block_and_missing_key_reports_change(
    tmp_path: Path,
) -> None:
    """Verify state=absent with legacy block removal reports changed=True without empty tables."""
    path = tmp_path / "config.toml"
    path.write_text(
        "[features]\ncodex_hooks = true\n\n"
        "# BEGIN ANSIBLE MANAGED BLOCK - sccache env\n"
        "[env]\n"
        'SCCACHE_DIR = "/old/cache"\n'
        "# END ANSIBLE MANAGED BLOCK - sccache env\n"
    )

    result = _run_module(
        toml_file,
        {"path": str(path), "key": "env.NONEXISTENT_KEY", "state": "absent"},
    )

    assert result["changed"] is True, (
        f"expected changed=True when legacy block was removed, got {result['changed']!r}"
    )
    rendered = path.read_text()
    assert "# BEGIN ANSIBLE MANAGED BLOCK - sccache env" not in rendered, (
        f"expected legacy block to be stripped, got {rendered!r}"
    )
    parsed = tomllib.loads(rendered)
    assert "env" not in parsed, (
        f"expected no spurious empty [env] table, got {rendered!r}"
    )


def test_toml_file_check_mode_toml_legacy_block_reports_changed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the CheckModeToml path reports changed=True when a legacy block is present."""
    path = tmp_path / "config.toml"
    path.write_text(
        '[env]\nPATH = "/usr/bin"\n\n'
        "# BEGIN ANSIBLE MANAGED BLOCK - sccache env\n"
        "[env]\n"
        'SCCACHE_DIR = "/old/cache"\n'
        "# END ANSIBLE MANAGED BLOCK - sccache env\n"
    )
    monkeypatch.setattr(
        toml_file,
        "import_tomlkit",
        lambda _module: (toml_file.CheckModeToml, tomllib.TOMLDecodeError),
    )

    contents_before = path.read_text()
    result = _run_module(
        toml_file,
        {
            "_ansible_check_mode": True,
            "path": str(path),
            "key": "env.SCCACHE_DIR",
            "value": "/home/leynos/.cache/sccache",
        },
    )

    assert result["changed"] is True
    assert path.read_text() == contents_before, "check mode must not write to disk"


def test_toml_file_check_mode_toml_absent_missing_key_reports_no_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the CheckModeToml path reports changed=False when state=absent and key is absent."""
    path = tmp_path / "config.toml"
    path.write_text("[features]\ncodex_hooks = true\n")
    monkeypatch.setattr(
        toml_file,
        "import_tomlkit",
        lambda _module: (toml_file.CheckModeToml, tomllib.TOMLDecodeError),
    )

    contents_before = path.read_text()
    result = _run_module(
        toml_file,
        {
            "_ansible_check_mode": True,
            "path": str(path),
            "key": "env.SCCACHE_DIR",
            "state": "absent",
        },
    )

    assert result["changed"] is False
    assert path.read_text() == contents_before, "check mode must not write to disk"


@pytest.mark.parametrize(
    ("module", "filename", "initial_content", "expected_value"),
    [
        (json_file, "config.json", '{"env": {"RUSTC_WRAPPER": "old"}}\n', "new"),
        (toml_file, "config.toml", '[env]\nRUSTC_WRAPPER = "old"\n', "new"),
    ],
)
def test_structured_file_modules_preserve_existing_mode_without_mode_argument(
    tmp_path: Path,
    module,
    filename: str,
    initial_content: str,
    expected_value: str,
) -> None:
    """Structured writes without mode should preserve an existing file mode."""
    path = tmp_path / filename
    path.write_text(initial_content)
    path.chmod(0o754)

    result = _run_module(
        module,
        {
            "path": str(path),
            "key": "env.RUSTC_WRAPPER",
            "value": expected_value,
        },
    )

    assert result["changed"] is True
    assert path.stat().st_mode & 0o7777 == 0o754


def test_sccache_environment_modules_write_expected_structures(tmp_path: Path) -> None:
    """Verify sccache env vars are written to the expected JSON and TOML structures."""
    expected_env = {
        "RUSTC_WRAPPER": "/home/leynos/.local/bin/notdeadyet",
        "RUSTC_HEARTBEAT_SECS": "45",
        "SCCACHE_DIR": "/home/leynos/.cache/sccache",
        "SCCACHE_CACHE_SIZE": "120G",
    }
    codex_path = tmp_path / "config.toml"
    claude_path = tmp_path / "settings.json"

    for key, value in expected_env.items():
        _run_module(
            toml_file,
            {"path": str(codex_path), "key": f"env.{key}", "value": value},
        )
        _run_module(
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


@pytest.mark.parametrize(
    ("subagent_parts", "config_parts", "expect_relative", "expected_value"),
    [
        (
            (".codex", "agents", "reviewer.toml"),
            (".codex", "config.toml"),
            True,
            str(Path("agents") / "reviewer.toml"),
        ),
        (
            ("shared", "reviewer.toml"),
            (".codex", "config.toml"),
            False,
            None,
        ),
        (
            (".codex", "agents", "bot.toml"),
            (".codex", "config.toml"),
            True,
            str(Path("agents") / "bot.toml"),
        ),
        (
            ("other", "bot.toml"),
            (".codex", "config.toml"),
            False,
            None,
        ),
    ],
)
def test_resolve_relative_config_file_parametrized(
    tmp_path: Path,
    subagent_parts: tuple[str, ...],
    config_parts: tuple[str, ...],
    expect_relative: bool,
    expected_value: str | None,
) -> None:
    """Paths inside config dir must be relative; outside paths must be absolute."""
    subagent_path = tmp_path.joinpath(*subagent_parts)
    config_path = tmp_path.joinpath(*config_parts)

    result = agent_config_common.resolve_relative_config_file(
        str(subagent_path), str(config_path)
    )

    if expect_relative:
        assert not Path(result).is_absolute(), f"expected relative path, got {result!r}"
        assert result == expected_value
    else:
        assert Path(result).is_absolute(), f"expected absolute path, got {result!r}"
        assert result == str(subagent_path)


@pytest.mark.parametrize("module", [json_file, toml_file])
def test_structured_file_modules_require_value_when_present(
    tmp_path: Path, module
) -> None:
    """Verify both structured-file modules reject state=present without a value."""
    _assert_fails(
        module,
        {"path": str(tmp_path / "config"), "key": "env.RUSTC_WRAPPER"},
        "value is required",
    )


@pytest.mark.parametrize("module", [json_file, toml_file])
def test_structured_file_modules_reject_non_octal_modes(tmp_path: Path, module) -> None:
    """Verify both structured-file modules reject a non-octal mode string."""
    path = tmp_path / "config"

    _assert_fails(
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
    """Verify json_file surfaces an atomic-write failure through fail_json."""

    def fail_write(path: str, content: str) -> None:
        """Raise a write failure for JSON write error coverage."""
        raise OSError("disk denied")

    monkeypatch.setattr(json_file, "atomic_write_text", fail_write)
    _assert_fails(
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
    """Verify toml_file surfaces an atomic-write failure through fail_json."""

    def fail_write(path: str, content: str) -> None:
        """Raise a write failure for TOML write error coverage."""
        raise OSError("disk denied")

    monkeypatch.setattr(toml_file, "atomic_write_text", fail_write)
    _assert_fails(
        toml_file,
        {
            "path": str(tmp_path / "config.toml"),
            "key": "env.SCCACHE_DIR",
            "value": "/home/leynos/.cache/sccache",
        },
        "Failed to write TOML file",
    )


def test_toml_file_reports_parse_errors(tmp_path: Path) -> None:
    """Verify toml_file converts a TOML parse error into a fail_json message."""

    class DummyModule:
        """Minimal module object that raises captured Ansible failures."""

        def fail_json(self, **kwargs) -> NoReturn:
            """Raise the captured parse failure payload."""
            raise AnsibleFailJson(kwargs)

    path = tmp_path / "config.toml"
    path.write_text("[env\n")
    tomlkit, parse_error = toml_file.import_tomlkit(DummyModule())

    with pytest.raises(AnsibleFailJson) as exc:
        toml_file.load_document(DummyModule(), tomlkit, parse_error, str(path))

    actual_message = exc.value.args[0]["msg"]
    assert "Failed to parse TOML file" in actual_message


def test_toml_file_does_not_mask_unexpected_parse_errors(tmp_path: Path) -> None:
    """Verify toml_file propagates unexpected parser exceptions without masking."""

    class DummyModule:
        """Minimal module object that raises captured Ansible failures."""

        def fail_json(self, **kwargs) -> NoReturn:
            """Raise the captured parse failure payload."""
            raise AnsibleFailJson(kwargs)

    class BrokenTomlkit:
        """Fake TOML implementation that raises an unexpected parse error."""

        @staticmethod
        def document() -> dict:
            """Return an empty TOML-like document."""
            return {}

        @staticmethod
        def parse(content: str) -> NoReturn:
            """Raise the unexpected parser error under test."""
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
    """Verify both modules surface an os.chmod failure through fail_json."""
    path = tmp_path / "config"
    path.write_text("{}\n" if module is json_file else "\n")

    def fail_chmod(path: str, mode: int) -> None:
        """Raise a chmod failure for structured file module coverage."""
        raise OSError("chmod denied")

    monkeypatch.setattr(module.os, "chmod", fail_chmod)
    _assert_fails(
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
    """Verify enforce_mode compares against 0o7777-masked bits, not 0o777."""
    path = tmp_path / "config"
    path.write_text("{}\n" if module is json_file else "\n")
    path.chmod(0o1777)

    changed = module.enforce_mode(FakeModule(), str(path), 0o1777)

    assert changed is False


@pytest.mark.parametrize("module", [json_file, toml_file])
def test_structured_file_modules_handle_special_bits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module
) -> None:
    """Special permission bits must not trigger repeated chmod attempts."""
    path = tmp_path / "config"
    expected_value = "/home/leynos/.local/bin/notdeadyet"
    path.write_text(
        json.dumps({"env": {"RUSTC_WRAPPER": expected_value}}) + "\n"
        if module is json_file
        else f'[env]\nRUSTC_WRAPPER = "{expected_value}"\n'
    )

    class StatResult:
        """Stat result containing the requested sticky permission bits."""

        st_mode = 0o1000 | 0o777

    def stat_with_special_bits(path: str) -> StatResult:
        """Return a stat result whose mode already matches the request."""
        return StatResult()

    def fail_chmod(path: str, mode: int) -> None:
        """Fail the test if chmod runs for an already matching mode."""
        raise AssertionError("chmod should not be called for matching special bits")

    class FakeOs:
        """Minimal os replacement exposing patched stat and chmod calls."""

        path = module.os.path
        stat = staticmethod(stat_with_special_bits)
        chmod = staticmethod(fail_chmod)

    monkeypatch.setattr(module, "os", FakeOs)

    result = _run_module(
        module,
        {
            "path": str(path),
            "key": "env.RUSTC_WRAPPER",
            "value": expected_value,
            "mode": "1777",
        },
    )

    assert result["changed"] is False


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
    """Verify JSON-hook modules create an entry, rerun idempotently, and remove it."""
    path = tmp_path / "settings.json"
    args = {
        "agent_executable": "/bin/sh",
        "path": str(path),
        "event": "Stop",
        "matcher": "Bash",
        "command": "run-checks",
        **extra_args,
    }

    result = _run_module(module, args)

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

    rerun_result = _run_module(module, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = _run_module(
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


def test_deepseek_tui_hook_writes_toml_and_removes_entry(tmp_path: Path) -> None:
    """Verify DeepSeek-TUI hooks are managed as TOML array-of-table entries."""
    path = tmp_path / "config.toml"
    args = {
        "path": str(path),
        "event": "shell_env",
        "name": "aws-creds",
        "command": "aws-vault export dev --format=env",
        "condition": {"type": "tool_category", "category": "shell"},
        "timeout_secs": 15,
        "enabled": True,
        "default_timeout_secs": 30,
    }

    result = _run_module(deepseek_tui_hook, args)

    assert result["changed"] is True
    assert result["hook"] == {
        "event": "shell_env",
        "command": "aws-vault export dev --format=env",
        "name": "aws-creds",
        "condition": {"type": "tool_category", "category": "shell"},
        "timeout_secs": 15,
    }
    rendered = path.read_text()
    parsed = tomllib.loads(rendered)
    assert parsed == {
        "hooks": {
            "enabled": True,
            "default_timeout_secs": 30,
            "hooks": [
                {
                    "event": "shell_env",
                    "command": "aws-vault export dev --format=env",
                    "name": "aws-creds",
                    "condition": {"type": "tool_category", "category": "shell"},
                    "timeout_secs": 15,
                }
            ],
        }
    }
    assert "[[hooks.hooks]]" in rendered

    rerun_result = _run_module(deepseek_tui_hook, args)
    assert rerun_result["changed"] is False

    absent = _run_module(
        deepseek_tui_hook,
        {
            "path": str(path),
            "event": "shell_env",
            "name": "aws-creds",
            "command": "aws-vault export dev --format=env",
            "state": "absent",
        },
    )
    assert absent["changed"] is True
    assert tomllib.loads(path.read_text()) == {
        "hooks": {"enabled": True, "default_timeout_secs": 30}
    }


def test_deepseek_tui_hook_absent_noop_does_not_return_synthetic_hooks(
    tmp_path: Path,
) -> None:
    """Verify absent no-op results reflect the unchanged on-disk TOML state."""
    path = tmp_path / "config.toml"

    result = _run_module(
        deepseek_tui_hook,
        {
            "path": str(path),
            "event": "shell_env",
            "name": "aws-creds",
            "command": "aws-vault export dev --format=env",
            "state": "absent",
        },
    )

    assert result["changed"] is False
    assert result["hooks"] == {}
    assert not path.exists(), f"expected absent no-op not to create {path}"


@pytest.mark.parametrize(
    ("module", "relative_path", "extra_args", "missing_field"),
    [
        (
            deepseek_tui_mcp,
            "mcp.json",
            {"name": "repo-tools"},
            "transport",
        ),
        (
            deepseek_tui_skill,
            "skills/repo-reviewer",
            {"name": "Repo reviewer"},
            "description",
        ),
    ],
)
def test_present_state_enforces_required_fields(
    tmp_path: Path,
    module,
    relative_path: str,
    extra_args: dict,
    missing_field: str,
) -> None:
    """Verify modules enforce required_if fields for state=present."""
    args = {"path": str(tmp_path / relative_path), **extra_args}
    _assert_fails(
        module,
        args,
        f"state is present but all of the following are missing: {missing_field}",
    )


def test_deepseek_tui_mcp_rejects_malformed_servers_root(tmp_path: Path) -> None:
    """Verify DeepSeek-TUI MCP rejects non-object servers data."""
    path = tmp_path / "mcp.json"
    path.write_text('{"servers": []}\n')

    _assert_fails(
        deepseek_tui_mcp,
        {
            "path": str(path),
            "name": "repo-tools",
            "transport": "stdio",
            "command": "repo-tools-mcp",
        },
        "Expected 'servers' to be a JSON object",
    )


@pytest.mark.parametrize(
    ("file_content", "read_error"),
    [
        ("{not json}\n", None),
        (None, OSError("permission denied")),
    ],
)
def test_deepseek_tui_mcp_reports_existing_data_read_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    file_content: str | None,
    read_error: OSError | None,
) -> None:
    """Verify DeepSeek-TUI MCP reports unreadable existing config with context."""
    path = tmp_path / "mcp.json"
    if file_content is not None:
        path.write_text(file_content)
    if read_error is not None:

        def fail_read_json(path: str, *, default: dict) -> NoReturn:
            raise read_error

        monkeypatch.setattr(deepseek_tui_mcp, "load_json_file", fail_read_json)

    set_module_args(
        {
            "path": str(path),
            "name": "repo-tools",
            "scope": "project",
            "transport": "stdio",
            "command": "repo-tools-mcp",
        }
    )
    with pytest.raises(AnsibleFailJson) as exc:
        deepseek_tui_mcp.main()

    message = exc.value.args[0]["msg"]
    assert "failed to read existing DeepSeek-TUI MCP data" in message
    assert "name='repo-tools'" in message
    assert "scope='project'" in message
    assert f"path={str(path)!r}" in message


def test_deepseek_tui_mcp_rejects_extra_managed_field_overrides(
    tmp_path: Path,
) -> None:
    """Verify DeepSeek-TUI MCP extra data cannot override managed fields."""
    _assert_fails(
        deepseek_tui_mcp,
        {
            "path": str(tmp_path / "mcp.json"),
            "name": "repo-tools",
            "transport": "stdio",
            "command": "repo-tools-mcp",
            "extra": {"command": "malicious-mcp"},
        },
        "extra cannot override managed MCP fields: command",
    )


def test_deepseek_tui_hook_rejects_malformed_hook_entries(tmp_path: Path) -> None:
    """Verify DeepSeek-TUI hook rejects malformed hooks.hooks TOML values."""
    path = tmp_path / "config.toml"
    path.write_text('[hooks]\nhooks = "bad"\n')

    _assert_fails(
        deepseek_tui_hook,
        {
            "path": str(path),
            "event": "shell_env",
            "name": "repo-env",
            "command": "repo-env export",
        },
        "Expected 'hooks.hooks' to be a list",
    )


def test_deepseek_tui_hook_rejects_extra_managed_field_overrides(
    tmp_path: Path,
) -> None:
    """Verify DeepSeek-TUI hook extra data cannot override managed fields."""
    _assert_fails(
        deepseek_tui_hook,
        {
            "path": str(tmp_path / "config.toml"),
            "event": "shell_env",
            "name": "repo-env",
            "command": "repo-env export",
            "extra": {"event": "session_start"},
        },
        "invalid extra keys for deepseek_tui_hook: event",
    )


def test_deepseek_tui_skill_resolves_workspace_preferred_path_and_scopes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify DeepSeek-TUI skill path resolution and removal semantics."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    project_result = _run_module(
        deepseek_tui_skill,
        {
            "name": "Repository reviewer",
            "scope": "project",
            "project_dir": str(project_dir),
            "description": "Review this repository.",
            "body": "Read AGENTS.md first.",
        },
    )

    expected_dir = project_dir / ".agents" / "skills" / "repository-reviewer"
    assert project_result["directory"] == str(expected_dir)
    assert (
        (expected_dir / "SKILL.md")
        .read_text()
        .startswith(
            '---\nname: "Repository reviewer"\ndescription: "Review this repository."'
        )
    )

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    user_result = _run_module(
        deepseek_tui_skill,
        {
            "name": "User reviewer",
            "scope": "user",
            "description": "Review user-scoped changes.",
        },
    )

    expected_user_dir = home / ".deepseek" / "skills" / "user-reviewer"
    assert user_result["directory"] == str(expected_user_dir)
    assert expected_user_dir.is_dir()
    assert (expected_user_dir / "SKILL.md").is_file()

    explicit_dir = tmp_path / "explicit-skill-dir"

    explicit_result = _run_module(
        deepseek_tui_skill,
        {
            "name": "Explicit reviewer",
            "path": str(explicit_dir),
            "scope": "project",
            "project_dir": str(project_dir),
            "description": "Review explicitly scoped changes.",
            "extra_files": {"references/checklist.md": "Check support files.\n"},
        },
    )

    assert explicit_result["directory"] == str(explicit_dir)
    assert explicit_dir.is_dir()
    assert (explicit_dir / "SKILL.md").is_file()
    assert (explicit_dir / "references" / "checklist.md").is_file()

    absent_result = _run_module(
        deepseek_tui_skill,
        {
            "name": "Explicit reviewer",
            "path": str(explicit_dir),
            "state": "absent",
        },
    )

    assert absent_result["changed"] is True
    assert absent_result["state_transition"] == "removed"
    assert not explicit_dir.exists()


def test_deepseek_tui_skill_metadata_cannot_override_managed_frontmatter(
    tmp_path: Path,
) -> None:
    """Verify DeepSeek-TUI skill metadata cannot override managed front matter."""
    path = tmp_path / "skills" / "repo-reviewer"

    result = _run_module(
        deepseek_tui_skill,
        {
            "path": str(path),
            "name": "Repo reviewer",
            "description": "Review repository changes.",
            "metadata": {
                "name": "Injected name",
                "description": "Injected description.",
                "owner": "release",
            },
        },
    )

    assert result["changed"] is True
    rendered = (path / "SKILL.md").read_text()
    assert 'name: "Repo reviewer"' in rendered
    assert 'description: "Review repository changes."' in rendered
    assert 'owner: "release"' in rendered
    assert "Injected name" not in rendered
    assert "Injected description." not in rendered


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

    result = _run_module(codex_cli_hook, args)

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

    rerun_result = _run_module(codex_cli_hook, args)
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

    result = _run_module(codex_cli_hook, args)

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
    rerun_result = _run_module(codex_cli_hook, args)
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
    """Verify subagent validation fails when the agent executable path is absent."""
    _assert_fails(
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
    """Verify the subagent module writes a TOML file and removes its registry entry."""
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

    result = _run_module(codex_cli_subagent, args)

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

    rerun_result = _run_module(codex_cli_subagent, args)
    assert rerun_result["changed"] is False, (
        f"expected idempotent rerun to report changed=False, got {rerun_result['changed']!r}"
    )

    absent = _run_module(
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
    assert "agents" not in absent, "expected absent result to use documented fields"
    assert absent["registry"] is None, "expected absent result registry to be None"
    assert not path.exists(), f"expected {path} to be removed"
    rendered_config_after_absent = config_path.read_text()
    assert rendered_config_after_absent == "\n", (
        f"expected config TOML file to contain only a newline, got {rendered_config_after_absent!r}"
    )


def test_codex_cli_subagent_rolls_back_file_when_registry_update_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the subagent module restores both snapshots when registry write fails."""
    config_path = tmp_path / "config.toml"
    path = tmp_path / "agents/reviewer.toml"

    def fail_registry(*args, **kwargs):
        """Raise the registry failure that should trigger rollback."""
        raise codex_cli_subagent.RegistryWriteError("registry denied")

    monkeypatch.setattr(codex_cli_subagent, "manage_named_toml_entry", fail_registry)
    _assert_fails(
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


def test_codex_cli_subagent_restore_snapshot_removes_expanded_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rollback removal should expand home-relative paths before deleting."""
    home = tmp_path / "home"
    target = home / ".codex" / "agents" / "reviewer.toml"
    monkeypatch.setenv("HOME", str(home))
    snapshot = codex_cli_subagent.snapshot_path(
        FakeModule(), "~/.codex/agents/reviewer.toml"
    )
    target.parent.mkdir(parents=True)
    target.write_text('name = "Reviewer"\n')

    codex_cli_subagent.restore_snapshot(FakeModule(), snapshot)

    assert not target.exists(), "expected rollback to remove the expanded path"


def test_codex_cli_subagent_restore_snapshot_preserves_mode(tmp_path: Path) -> None:
    """Rollback restore should put file content and mode back together."""
    path = tmp_path / "agents/reviewer.toml"
    path.parent.mkdir(parents=True)
    path.write_text('name = "Reviewer"\n')
    path.chmod(0o640)
    snapshot = codex_cli_subagent.snapshot_path(FakeModule(), str(path))
    path.write_text('name = "Changed"\n')
    path.chmod(0o600)

    codex_cli_subagent.restore_snapshot(FakeModule(), snapshot)

    assert path.read_text() == 'name = "Reviewer"\n'
    assert path.stat().st_mode & 0o7777 == 0o640


def test_codex_cli_subagent_reraises_unexpected_registry_update_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify non-RegistryWriteError exceptions propagate from registry update."""
    config_path = tmp_path / "config.toml"
    path = tmp_path / "agents/reviewer.toml"

    def fail_registry(*args, **kwargs):
        """Raise an unexpected registry update failure."""
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
    """Verify non-RegistryWriteError exceptions propagate from registry removal."""
    config_path = tmp_path / "config.toml"
    path = tmp_path / "agents/reviewer.toml"

    def fail_registry(*args, **kwargs):
        """Raise an unexpected registry removal failure."""
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


def test_codex_cli_subagent_reraises_non_ansible_exceptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-Ansible failure exceptions must propagate, not be swallowed."""

    def fail_registry(*args, **kwargs):
        """Raise an unexpected registry failure."""
        raise RuntimeError("boom")

    monkeypatch.setattr(codex_cli_subagent, "manage_named_toml_entry", fail_registry)
    with pytest.raises(RuntimeError, match="boom"):
        _run_module(
            codex_cli_subagent,
            {
                "name": "test",
                "path": str(tmp_path / "agents/test.toml"),
                "config_path": str(tmp_path / "config.toml"),
                "state": "present",
                "developer_instructions": "x",
                "description": "y",
            },
        )


def test_codex_cli_subagent_requires_present_fields(tmp_path: Path) -> None:
    """Verify the subagent module rejects state=present without required fields."""
    _assert_fails(
        codex_cli_subagent,
        {
            "name": "Reviewer",
            "path": str(tmp_path / "reviewer.toml"),
            "description": "Review changes.",
        },
        "developer_instructions is required",
    )
