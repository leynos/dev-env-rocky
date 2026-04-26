"""Provide shared pytest fixtures for packaging.tools module tests.

This conftest.py module patches ``ansible.module_utils.basic.AnsibleModule``
so tests can call packaging modules in-process and capture ``exit_json`` or
``fail_json`` through ``module_test_utils`` helpers.

Example test usage::

    result = run_module(my_module, {"name": "ruff", "state": "present"})
    assert result["changed"] is True
"""

from __future__ import annotations

import pytest
from ansible.module_utils import basic

from ansible_collections.packaging.tools.tests.unit.plugins.modules.module_test_utils import (
    exit_json,
    fail_json,
)


@pytest.fixture(autouse=True)
def patch_ansible_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)
    monkeypatch.setattr(basic, "_ANSIBLE_ARGS", None)
