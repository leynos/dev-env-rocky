"""Shared fixtures for repository-level tests."""

import pytest  # ty: ignore[unresolved-import]
from ansible.module_utils import basic  # ty: ignore[unresolved-import]
from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules import (
    module_test_utils,
)


@pytest.fixture(autouse=True)
def patch_ansible_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch AnsibleModule exits so repository tests can run modules in-process."""
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", module_test_utils.exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", module_test_utils.fail_json)
    monkeypatch.setattr(basic, "_ANSIBLE_ARGS", None)
