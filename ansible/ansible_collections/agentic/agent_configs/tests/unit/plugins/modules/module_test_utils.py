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
    payload = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(payload)


def exit_json(*args: Any, **kwargs: Any) -> None:
    if "changed" not in kwargs:
        kwargs["changed"] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args: Any, **kwargs: Any) -> None:
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


@dataclass
class FakeModule:
    check_mode: bool = False
    params: dict[str, Any] | None = None

    def fail_json(self, **kwargs: Any) -> None:
        kwargs["failed"] = True
        raise AnsibleFailJson(kwargs)
