"""Provide Ansible module execution helpers for agent_configs unit tests.

The helpers in this module serialize module arguments into Ansible's global
test input slot and replace ``exit_json`` or ``fail_json`` with exceptions that
tests can assert against. The package ``conftest.py`` fixture installs those
helpers on ``AnsibleModule`` for in-process module tests, while direct helper
tests can use ``FakeModule`` when constructing a full Ansible module would add
unnecessary setup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import pytest
from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes


class AnsibleExitJson(Exception):
    """Raised when a module calls exit_json during unit tests."""


class AnsibleFailJson(Exception):
    """Raised when a module calls fail_json during unit tests."""

class _ModuleEntryPoint(Protocol):
    """Structural protocol for Ansible module modules used by tests."""

    def main(self) -> None:
        """Run the module entrypoint."""
def set_module_args(args: dict[str, object]) -> None:
    """Serialize Ansible module arguments into the global test input slot."""
    payload = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(payload)
    basic._ANSIBLE_PROFILE = "legacy"


def exit_json(*args: object, **kwargs: object) -> None:
    """Raise the captured successful module result instead of exiting."""
    if "changed" not in kwargs:
        kwargs["changed"] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args: object, **kwargs: object) -> None:
    """Raise the captured failed module result instead of exiting."""
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


@dataclass
class FakeModule:
    """Minimal AnsibleModule replacement for direct helper tests."""

    check_mode: bool = False
    params: dict[str, object] | None = None

    def fail_json(self, **kwargs: object) -> None:
        """Raise the captured failure result for helper-level assertions."""
        kwargs["failed"] = True
        raise AnsibleFailJson(kwargs)

def run_module(module: _ModuleEntryPoint, args: dict[str, object]) -> dict:
    """Run an Ansible module in-process and return its exit payload."""
    set_module_args(args)
    with pytest.raises(AnsibleExitJson) as exc:
        module.main()
    return exc.value.args[0]

def assert_module_fails(
    module: _ModuleEntryPoint, args: dict[str, object], message: str
) -> None:
    """Assert that an Ansible module fails with a message containing *message*."""
    set_module_args(args)
    with pytest.raises(AnsibleFailJson) as exc:
        module.main()
    actual_message = exc.value.args[0]["msg"]
    assert message in actual_message, (
        f"expected failure message to contain {message!r}, got {actual_message!r}"
    )
