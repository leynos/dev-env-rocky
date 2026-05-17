"""Unit tests for the codex_cli_hook and codex_cli_subagent modules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ansible_collections.agentic.agent_configs.plugins.modules import (
    claude_code_hook,
    codex_cli_hook,
    codex_cli_subagent,
)
from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    AnsibleExitJson,
    FakeModule,
    assert_module_fails,
    run_module,
    set_module_args,
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
    """Verify subagent validation fails when the agent executable path is absent."""
    assert_module_fails(
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
    assert_module_fails(
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
        run_module(
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
    assert_module_fails(
        codex_cli_subagent,
        {
            "name": "Reviewer",
            "path": str(tmp_path / "reviewer.toml"),
            "description": "Review changes.",
        },
        "developer_instructions is required",
    )
