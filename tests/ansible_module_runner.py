"""Shared helpers for in-process Ansible module tests."""

import typing as typ
from types import ModuleType

import pytest  # ty: ignore[unresolved-import]
from ansible_collections.agentic.agent_configs.tests.unit.plugins.modules import (
    module_test_utils,
)


class AnsibleModuleEntrypoint(typ.Protocol):
    """Minimal protocol for modules exercised through their Ansible entrypoint."""

    def main(self) -> None:
        """Run the Ansible module entrypoint."""


def run_module(
    module: ModuleType | AnsibleModuleEntrypoint,
    args: dict[str, object],
) -> dict[str, object]:
    """Run an Ansible module in-process and return its exit payload."""
    module_test_utils.set_module_args(args)
    with pytest.raises(module_test_utils.AnsibleExitJson) as exc:
        module.main()
    return typ.cast("dict[str, object]", exc.value.args[0])
