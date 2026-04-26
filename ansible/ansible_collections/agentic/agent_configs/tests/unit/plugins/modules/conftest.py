"""Provide shared pytest fixtures for Ansible module unit tests.

This conftest.py module patches ``AnsibleModule.exit_json`` and
``AnsibleModule.fail_json`` for every test in the modules test package so
custom Ansible modules can be executed in-process. Tests use the helpers from
``module_test_utils`` to run a module and then assert against the captured
result instead of allowing Ansible to terminate the interpreter.

Example test usage::

    result = run_module(my_module, {"name": "ruff", "state": "present"})
    assert result["changed"] is True
"""

from __future__ import annotations

import pytest
from ansible.module_utils import basic

from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    exit_json,
    fail_json,
)


@pytest.fixture(autouse=True)
def patch_ansible_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)
    monkeypatch.setattr(basic, "_ANSIBLE_ARGS", None)
