#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Manage Factory Droid custom model definitions.

The factory_droid_model.py Ansible module creates, updates, or removes entries
from Factory Droid's ``customModels`` list in ``~/.factory/settings.json`` by
default. Factory's BYOK configuration uses these entries to route Droid model
requests to OpenAI-compatible or Anthropic-compatible endpoints.

Example playbook task::

    - name: Configure a DeepSeek Anthropic-compatible model
      agentic.agent_configs.factory_droid_model:
        model: deepseek-v4-pro
        display_name: DeepSeek V4 Pro
        provider: anthropic
        base_url: https://api.deepseek.com/anthropic
        api_key: "{{ deepseek_api_key }}"
"""
# Copyright: (c) 2026, Leynos
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: factory_droid_model
short_description: Manage Factory Droid custom models
version_added: "1.0.0"
description:
  - Manage Factory Droid BYOK custom model entries in C(~/.factory/settings.json) or a supplied JSON path.
  - Entries are keyed by their C(model) value inside the C(customModels) list.
options:
  model:
    description:
      - Model identifier passed to Factory Droid.
    type: str
    required: true
  state:
    description:
      - Whether the custom model entry should exist.
    type: str
    choices: [present, absent]
    default: present
  path:
    description:
      - Exact Factory Droid settings JSON path to manage.
    type: path
    default: ~/.factory/settings.json
  display_name:
    description:
      - Human-readable model label shown by Droid.
    type: str
  provider:
    description:
      - Provider compatibility mode.
    type: str
    choices: [anthropic, openai]
    default: anthropic
  base_url:
    description:
      - Provider base URL for the custom model.
    type: str
  api_key:
    description:
      - API key for the custom model provider.
    type: str
  max_output_tokens:
    description:
      - Optional maximum output token setting.
    type: int
  extra:
    description:
      - Additional raw keys to merge into the custom model definition.
    type: dict
    default: {}
author:
  - Leynos Project (@leynos)
"""

EXAMPLES = r"""
- name: Configure DeepSeek V4 Pro through the Anthropic-compatible endpoint
  agentic.agent_configs.factory_droid_model:
    model: deepseek-v4-pro
    display_name: DeepSeek V4 Pro
    provider: anthropic
    base_url: https://api.deepseek.com/anthropic
    api_key: "{{ deepseek_api_key }}"

- name: Remove a custom Droid model
  agentic.agent_configs.factory_droid_model:
    model: deepseek-v4-pro
    state: absent
"""

RETURN = r"""
path:
  description: Managed Factory Droid settings path.
  returned: always
  type: str
custom_model:
  description: Effective custom model definition.
  returned: when state == 'present'
  type: dict
"""

from typing import Any

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.agentic.agent_configs.plugins.module_utils.agent_config_common import (
    clean_dict,
    expand_path,
    load_json_file,
    log_operation,
    write_json_if_changed,
)


def build_custom_model(module: AnsibleModule) -> dict[str, Any]:
    """Build a Factory Droid custom model definition from module parameters."""
    params = module.params
    missing = [
        name
        for name in ("display_name", "base_url", "api_key")
        if not params.get(name)
    ]
    if missing:
        module.fail_json(
            msg="%s required when state=present" % ", ".join(sorted(missing))
        )

    desired = {
        "model": params["model"],
        "displayName": params.get("display_name"),
        "baseUrl": params.get("base_url"),
        "apiKey": params.get("api_key"),
        "provider": params.get("provider"),
        "maxOutputTokens": params.get("max_output_tokens"),
    }
    desired.update(params.get("extra") or {})
    return clean_dict(desired)


def model_index(custom_models: list[Any], model: str) -> int | None:
    """Return the list index for a custom model id, if present."""
    for index, item in enumerate(custom_models):
        if isinstance(item, dict) and item.get("model") == model:
            return index
    return None


def manage_custom_model(
    module: AnsibleModule,
    path: str,
    model: str,
    desired: dict[str, Any] | None,
    state: str,
) -> tuple[bool, dict[str, Any], dict[str, Any] | None]:
    """Create, update, or remove a Factory Droid custom model entry."""
    path = expand_path(path)
    data = load_json_file(path, default={})
    if not isinstance(data, dict):
        module.fail_json(msg="Expected JSON object in %s" % path)

    custom_models = data.setdefault("customModels", [])
    if not isinstance(custom_models, list):
        module.fail_json(msg="Expected 'customModels' to be a list in %s" % path)

    index = model_index(custom_models, model)
    changed = False
    effective = desired
    if state == "present":
        if index is None:
            custom_models.append(desired)
            changed = True
        elif custom_models[index] != desired:
            custom_models[index] = desired
            changed = True
    elif index is not None:
        removed = custom_models.pop(index)
        effective = removed if isinstance(removed, dict) else None
        changed = True

    if changed:
        if module.check_mode:
            log_operation(
                module,
                "factory_droid_model",
                path=path,
                model=model,
                state=state,
                changed=True,
                check_mode=True,
            )
            return True, data, effective
        write_json_if_changed(module, path, data)

    log_operation(
        module,
        "factory_droid_model",
        path=path,
        model=model,
        state=state,
        changed=changed,
    )
    return changed, data, effective


def main() -> None:
    """Run the Ansible module."""
    module = AnsibleModule(
        argument_spec={
            "model": {"type": "str", "required": True},
            "state": {
                "type": "str",
                "choices": ["present", "absent"],
                "default": "present",
            },
            "path": {"type": "path", "default": "~/.factory/settings.json"},
            "display_name": {"type": "str"},
            "provider": {
                "type": "str",
                "choices": ["anthropic", "openai"],
                "default": "anthropic",
            },
            "base_url": {"type": "str"},
            "api_key": {"type": "str", "no_log": True},
            "max_output_tokens": {"type": "int"},
            "extra": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )

    desired = None
    if module.params["state"] == "present":
        desired = build_custom_model(module)

    changed, _, effective = manage_custom_model(
        module=module,
        path=module.params["path"],
        model=module.params["model"],
        desired=desired,
        state=module.params["state"],
    )

    result = {
        "changed": changed,
        "path": expand_path(module.params["path"]),
        "model": module.params["model"],
    }
    if module.params["state"] == "present" and effective:
        redacted = {**effective, "apiKey": "REDACTED"} if "apiKey" in effective else effective
        result["custom_model"] = redacted

    module.exit_json(**result)


if __name__ == "__main__":
    main()
