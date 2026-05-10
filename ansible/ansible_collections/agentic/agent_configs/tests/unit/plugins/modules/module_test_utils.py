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
from typing import Any

from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes


class AnsibleExitJson(Exception):
    """Raised when a module calls exit_json during unit tests."""


class AnsibleFailJson(Exception):
    """Raised when a module calls fail_json during unit tests."""


def set_module_args(args: dict[str, Any]) -> None:
    """Serialize Ansible module arguments into the global test input slot."""
    payload = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(payload)


def exit_json(*args: Any, **kwargs: Any) -> None:
    """Raise the captured successful module result instead of exiting."""
    if "changed" not in kwargs:
        kwargs["changed"] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args: Any, **kwargs: Any) -> None:
    """Raise the captured failed module result instead of exiting."""
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


@dataclass
class FakeModule:
    """Minimal AnsibleModule replacement for direct helper tests."""

    check_mode: bool = False
    params: dict[str, Any] | None = None

    def fail_json(self, **kwargs: Any) -> None:
        """Raise the captured failure result for helper-level assertions."""
        kwargs["failed"] = True
        raise AnsibleFailJson(kwargs)
