"""Provide Ansible module execution helpers for packaging.tools unit tests.

The helpers in this module serialize module arguments into Ansible's global
test input slot and replace ``exit_json`` or ``fail_json`` with exceptions that
tests can assert against. The package ``conftest.py`` fixture installs those
helpers on ``AnsibleModule`` so tests can execute packaging modules in-process
without allowing Ansible to terminate the interpreter.
"""

from __future__ import annotations

import json
from typing import Any

from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes


class AnsibleExitJson(Exception):
    """Raised when a module calls exit_json during unit tests."""


class AnsibleFailJson(Exception):
    """Raised when a module calls fail_json during unit tests."""


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
