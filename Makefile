.PHONY: site check

ANSIBLE_COLLECTIONS_PATH ?= ./ansible/ansible_collections
ANSIBLE_CONFIG ?= ./ansible/ansible.cfg
ANSIBLE_LIBRARY ?= ./ansible/ansible_collections/packaging/tools/plugins/modules:./ansible/ansible_collections/agentic/agent_configs/plugins/modules
ANSIBLE_MODULE_UTILS ?= ./ansible/ansible_collections/agentic/agent_configs/plugins/module_utils

site:
	ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) \
          ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) \
          ANSIBLE_LIBRARY=$(ANSIBLE_LIBRARY) \
          ANSIBLE_MODULE_UTILS=$(ANSIBLE_MODULE_UTILS) \
          ansible-playbook -i ansible/inventory.ini ansible/site.yml

check:
	ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) \
          ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) \
          ANSIBLE_LIBRARY=$(ANSIBLE_LIBRARY) \
          ANSIBLE_MODULE_UTILS=$(ANSIBLE_MODULE_UTILS) \
          ansible-playbook -i ansible/inventory.ini ansible/site.yml --check --diff
