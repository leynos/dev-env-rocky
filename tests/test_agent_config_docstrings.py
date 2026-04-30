"""Docstring coverage checks for agent configuration helper modules."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCSTRING_TARGETS = [
    REPO_ROOT
    / "ansible/ansible_collections/agentic/agent_configs/plugins/modules/json_file.py",
    REPO_ROOT
    / "ansible/ansible_collections/agentic/agent_configs/plugins/modules/toml_file.py",
    REPO_ROOT
    / "ansible/ansible_collections/agentic/agent_configs/plugins/modules/codex_cli_subagent.py",
    REPO_ROOT
    / "ansible/ansible_collections/agentic/agent_configs/plugins/module_utils/agent_config_common.py",
]


def test_agent_config_helpers_have_docstrings() -> None:
    missing: list[str] = []
    for path in DOCSTRING_TARGETS:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.ClassDef, ast.FunctionDef))
                and ast.get_docstring(node) is None
            ):
                missing.append(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno}:{node.name}"
                )

    assert not missing, "missing docstrings:\n" + "\n".join(sorted(missing))
