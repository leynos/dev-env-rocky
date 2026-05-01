"""Regression tests for the sccache user role task definitions."""

import json
from pathlib import Path
import re
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]
SCCACHE_USER_TASKS = REPO_ROOT / "ansible/roles/sccache_user/tasks/main.yml"
SCCACHE_USER_DEFAULTS = REPO_ROOT / "ansible/roles/sccache_user/defaults/main.yml"
EXPECTED_ENV = {
    "RUSTC_WRAPPER": "{{ ansible_env.HOME }}/.local/bin/notdeadyet",
    "RUSTC_HEARTBEAT_SECS": "45",
    "SCCACHE_DIR": "{{ ansible_env.HOME }}/.cache/sccache",
    "SCCACHE_CACHE_SIZE": "120G",
}


def extract_task(content: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^- name: {re.escape(name)}\n(?P<body>.*?)(?=^- name: |\Z)", content
    )
    assert match, f"expected task named {name!r} to exist"
    return match.group("body")


def test_sccache_user_role_uses_structured_config_modules() -> None:
    content = SCCACHE_USER_TASKS.read_text()
    codex_task = extract_task(content, "Configure sccache environment in Codex config")
    claude_task = extract_task(
        content, "Configure sccache environment in Claude settings"
    )

    assert "ansible.builtin.blockinfile" not in content, (
        "sccache_user must manage Codex and Claude settings with structured "
        "file modules instead of fragile text blocks"
    )
    assert "agentic.agent_configs.toml_file" in codex_task, (
        "sccache_user must manage Codex config.toml through the toml_file module"
    )
    assert "agentic.agent_configs.json_file" in claude_task, (
        "sccache_user must manage Claude settings.json through the json_file module"
    )
    assert "{{ ansible_env.HOME }}/.codex/config.toml" in codex_task, (
        "sccache_user must write Codex environment settings to config.toml"
    )
    assert "{{ ansible_env.HOME }}/.claude/settings.json" in claude_task, (
        "sccache_user must write Claude environment settings to settings.json"
    )


def test_sccache_user_role_writes_expected_environment_structure() -> None:
    content = SCCACHE_USER_TASKS.read_text()
    defaults = SCCACHE_USER_DEFAULTS.read_text()
    codex_task = extract_task(content, "Configure sccache environment in Codex config")
    claude_task = extract_task(
        content, "Configure sccache environment in Claude settings"
    )
    codex_toml = "[env]\n" + "\n".join(
        f'{key} = "{value}"' for key, value in EXPECTED_ENV.items()
    )
    claude_json = json.dumps({"env": EXPECTED_ENV})

    assert tomllib.loads(codex_toml)["env"] == EXPECTED_ENV, (
        "expected sccache_user Codex values to form a valid TOML [env] table"
    )
    assert json.loads(claude_json)["env"] == EXPECTED_ENV, (
        "expected sccache_user Claude values to form a valid JSON env object"
    )
    assert 'loop: "{{ sccache_env_vars }}"' in codex_task, (
        "expected Codex task to use the shared sccache_env_vars role default"
    )
    assert 'loop: "{{ sccache_env_vars }}"' in claude_task, (
        "expected Claude task to use the shared sccache_env_vars role default"
    )
    for key, value in EXPECTED_ENV.items():
        expected_key = f"- key: {key}"
        expected_value = f'value: "{value}"'
        assert expected_key in defaults, (
            f"expected sccache_env_vars default to include {expected_key!r}"
        )
        assert expected_value in defaults, (
            f"expected sccache_env_vars default to include {expected_value!r}"
        )


def test_sccache_user_role_removes_obsolete_claude_toml_config() -> None:
    content = SCCACHE_USER_TASKS.read_text()
    task = extract_task(content, "Remove obsolete Claude TOML config")

    assert "{{ ansible_env.HOME }}/.claude/config.toml" in task, (
        "sccache_user must clean up the obsolete invalid Claude TOML config"
    )
    assert "state: absent" in task, (
        "sccache_user must remove the obsolete Claude config.toml"
    )
