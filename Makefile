.PHONY: site check

ANSIBLE_COLLECTIONS_PATH ?= ./ansible/ansible_collections
ANSIBLE_CONFIG ?= ./ansible/ansible.cfg

site:
	ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) \
          ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ansible-playbook -i ansible/inventory.ini ansible/site.yml

check:
	ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) \
          ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ansible-playbook -i ansible/inventory.ini ansible/site.yml --check --diff
