MDLINT ?= markdownlint-cli2
NIXIE ?= nixie
MDFORMAT_ALL ?= mdformat-all
MOLECULE ?= molecule
PYTHON_PACKAGE_DIR ?= python/rust_cleanup
PYTHON_PATHS = $(PYTHON_PACKAGE_DIR)/src $(PYTHON_PACKAGE_DIR)/tests tests
MARKDOWN_PATHS = AGENTS.md .rules/*.md docs/*.md ansible/roles/agent_tools/files/AGENTS.md $(PYTHON_PACKAGE_DIR)/README.md
ANSIBLE_COLLECTIONS_ROOT = $(CURDIR)/ansible/ansible_collections
TOOLS = ruff ty $(MDLINT) $(MDFORMAT_ALL) uv
UV_ENV = PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 UV_CACHE_DIR=.uv-cache UV_TOOL_DIR=.uv-tools
PYTEST_XDIST_WORKERS ?= 1

.PHONY: help site check lint fmt check-fmt markdownlint molecule nixie test typecheck \
        $(TOOLS)

ANSIBLE_COLLECTIONS_PATH ?= ./ansible/ansible_collections
ANSIBLE_CONFIG ?= ./ansible/ansible.cfg
ANSIBLE_LIBRARY ?= ./ansible/ansible_collections/packaging/tools/plugins/modules:./ansible/ansible_collections/agentic/agent_configs/plugins/modules
ANSIBLE_MODULE_UTILS ?= ./ansible/ansible_collections/agentic/agent_configs/plugins/module_utils

define ensure_tool
	@command -v $(1) >/dev/null 2>&1 || { \
	  printf "Error: '%s' is required, but not installed\n" "$(1)" >&2; \
	  exit 1; \
	}
endef

ifneq ($(strip $(TOOLS)),)
$(TOOLS): ## Verify required CLI tools
	$(call ensure_tool,$@)
endif

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

fmt: ruff $(MDFORMAT_ALL) ## Format Python and Markdown sources
	ruff format $(PYTHON_PATHS)
	ruff check --select I --fix $(PYTHON_PATHS)
	$(MDFORMAT_ALL) $(MARKDOWN_PATHS)

check-fmt: ruff ## Verify Python formatting
	ruff format --check $(PYTHON_PATHS)

lint: ruff ## Run Python linters
	ruff check $(PYTHON_PATHS)

typecheck: uv ## Run Python typechecking
	$(UV_ENV) uv run --directory $(PYTHON_PACKAGE_DIR) --project . --group dev --with ty ty --version
	$(UV_ENV) uv run --directory $(PYTHON_PACKAGE_DIR) --project . --group dev --with ty ty check src tests
	$(UV_ENV) uv run --with pytest --with pyyaml --with ty ty check tests

markdownlint: $(MDLINT) ## Lint Markdown files
	$(MDLINT) $(MARKDOWN_PATHS)

molecule: ## Run Ansible role Molecule tests
	cd ansible/roles/node_packages && \
	  ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_ROOT):~/.ansible/collections:/usr/share/ansible/collections \
	  ANSIBLE_LIBRARY=$(ANSIBLE_COLLECTIONS_ROOT)/packaging/tools/plugins/modules:$(ANSIBLE_COLLECTIONS_ROOT)/agentic/agent_configs/plugins/modules \
	  ANSIBLE_MODULE_UTILS=$(ANSIBLE_COLLECTIONS_ROOT)/agentic/agent_configs/plugins/module_utils \
	  $(MOLECULE) test -s rocky10
	cd ansible/roles/paths && $(MOLECULE) test -s rocky10
	cd ansible/roles/coderabbit_cli && $(MOLECULE) test -s rocky10

nixie: ## Validate Mermaid diagrams
	$(call ensure_tool,$(NIXIE))
	$(NIXIE) --no-sandbox

test: uv ## Run Python tests
	$(UV_ENV) uv run --project $(PYTHON_PACKAGE_DIR) --group dev pytest -v $(PYTHON_PACKAGE_DIR)/tests
	$(UV_ENV) uv run --with pytest --with pyyaml pytest -v tests

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS=":"; printf "Available targets:\n"} {printf "  %-20s %s\n", $$1, $$2}'
