"""Shared helpers for in-process Ansible module tests."""

from types import ModuleType
from typing import Protocol, cast

import pytest  # ty: ignore[unresolved-import]
from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules.module_test_utils import (
    AnsibleExitJson,
    set_module_args,
)


class AnsibleModuleEntrypoint(Protocol):
    """Minimal protocol for modules exercised through their Ansible entrypoint."""

    def main(self) -> None:
        """Run the Ansible module entrypoint."""


def run_module(
    module: ModuleType | AnsibleModuleEntrypoint,
    args: dict[str, object],
) -> dict[str, object]:
    """Run an Ansible module in-process and return its exit payload."""
    set_module_args(args)
    with pytest.raises(AnsibleExitJson) as exc:
        module.main()
    return cast(dict[str, object], exc.value.args[0])
