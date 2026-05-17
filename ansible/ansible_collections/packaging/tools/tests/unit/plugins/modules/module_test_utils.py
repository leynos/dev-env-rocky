"""Provide Ansible module execution helpers for packaging.tools unit tests.

The helpers in this module serialize module arguments into Ansible's global
test input slot and replace ``exit_json`` or ``fail_json`` with exceptions that
tests can assert against. The package ``conftest.py`` fixture installs those
helpers on ``AnsibleModule`` so tests can execute packaging modules in-process
without allowing Ansible to terminate the interpreter.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import pytest

from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes


class AnsibleExitJson(Exception):
    """Raised when a module calls exit_json during unit tests."""


class AnsibleFailJson(Exception):
    """Raised when a module calls fail_json during unit tests."""


class _ModuleWithMain(Protocol):
    """Protocol for modules executed through the unit-test harness."""

    def main(self) -> None: ...


def set_module_args(args: dict[str, Any]) -> None:
    payload = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(payload)
    basic._ANSIBLE_PROFILE = "legacy"


def exit_json(*args: Any, **kwargs: Any) -> None:
    if "changed" not in kwargs:
        kwargs["changed"] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args: Any, **kwargs: Any) -> None:
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


def run_module(module: _ModuleWithMain, args: dict[str, object]) -> dict[str, object]:
    """Call module.main() with args and return the exit payload."""
    set_module_args(args)
    with pytest.raises(AnsibleExitJson) as exc:
        module.main()
    return exc.value.args[0]


def assert_equal(actual: object, expected: object, context: str) -> None:
    """Assert equality with a diagnostic message."""
    assert actual == expected, f"{context}: expected {expected!r}, got {actual!r}"


def assert_is(actual: object, expected: object, context: str) -> None:
    """Assert identity with a diagnostic message."""
    assert actual is expected, f"{context}: expected {expected!r}, got {actual!r}"
