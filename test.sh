#!/usr/bin/env bash
# test.sh - Test the bootstrap scripts in a Fedora 43 container
#
# This script runs shiny-new-pc.sh in a disposable Podman container to
# verify the installation process works without breaking anything on
# the host system.
#
# Usage:
#     ./test.sh
#
# What it does:
#   1. Creates a Fedora 43 container with the repo mounted
#   2. Runs the bootstrap script (with non-interactive git config)
#   3. Performs sanity checks on installed tools
#   4. Reports results and offers cleanup instructions
#
# Exit codes:
#     0  All tests passed
#     1  Test failed or container error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_NAME="dev-env-fedora-test-$$"
IMAGE="registry.fedoraproject.org/fedora:43"
WORKDIR="/root/dev-env-fedora"

# Trap to print container name on failure
on_error() {
    echo
    echo -e "\033[0;31m════════════════════════════════════════════════════════════════\033[0m"
    echo -e "\033[0;31m  Test failed! Container preserved: ${CONTAINER_NAME}\033[0m"
    echo -e "\033[0;31m════════════════════════════════════════════════════════════════\033[0m"
    echo
    echo "To debug:"
    echo "    podman exec -it ${CONTAINER_NAME} bash"
    echo
    echo "To clean up:"
    echo "    podman stop ${CONTAINER_NAME} && podman rm ${CONTAINER_NAME}"
}
trap on_error ERR

# Colours for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

section() {
    echo
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

fail() {
    echo -e "${RED}✗ $1${NC}"
}

cleanup_instructions() {
    echo
    echo -e "${YELLOW}Container '${CONTAINER_NAME}' is still running for inspection.${NC}"
    echo
    echo "To explore the container:"
    echo "    podman exec -it ${CONTAINER_NAME} bash"
    echo
    echo "To view logs:"
    echo "    podman logs ${CONTAINER_NAME}"
    echo
    echo "To stop and remove the container:"
    echo "    podman stop ${CONTAINER_NAME} && podman rm ${CONTAINER_NAME}"
    echo
    echo "To remove the Fedora image as well:"
    echo "    podman rmi ${IMAGE}"
}

# ------------------------------------------------------------------------------
section "Pulling Fedora 43 image"
# ------------------------------------------------------------------------------

podman pull "${IMAGE}"

# ------------------------------------------------------------------------------
section "Starting test container"
# ------------------------------------------------------------------------------

podman run -d \
    --name "${CONTAINER_NAME}" \
    "${IMAGE}" \
    sleep infinity

success "Container '${CONTAINER_NAME}' started"

# ------------------------------------------------------------------------------
section "Copying workspace to container"
# ------------------------------------------------------------------------------

podman cp "${SCRIPT_DIR}" "${CONTAINER_NAME}:${WORKDIR}"
success "Workspace copied to ${WORKDIR}"

# ------------------------------------------------------------------------------
section "Installing prerequisites"
# ------------------------------------------------------------------------------

# Install minimal deps needed before the main script runs
podman exec "${CONTAINER_NAME}" dnf install -y curl wget tar gzip sudo git

# ------------------------------------------------------------------------------
section "Configuring Git (non-interactive)"
# ------------------------------------------------------------------------------

# Pre-configure git to skip the interactive prompt in git-setup
podman exec "${CONTAINER_NAME}" git config --global user.name "Test User"
podman exec "${CONTAINER_NAME}" git config --global user.email "test@example.com"

# Create a modified git-setup that skips the prompts since we pre-configured
podman exec "${CONTAINER_NAME}" bash -c "
    sed -e '/^# Prompt for user identity/,/^git config --global user.email/d' \
        ${WORKDIR}/bin/git-setup > ${WORKDIR}/bin/git-setup-test
    chmod +x ${WORKDIR}/bin/git-setup-test
"

# ------------------------------------------------------------------------------
section "Running bootstrap script"
# ------------------------------------------------------------------------------

# Run the main script, but use the non-interactive git-setup
# We need to modify shiny-new-pc.sh temporarily to use git-setup-test
podman exec "${CONTAINER_NAME}" bash -c "
    cd ${WORKDIR}
    sed 's|git-setup|git-setup-test|g' shiny-new-pc.sh > shiny-new-pc-test.sh
    chmod +x shiny-new-pc-test.sh
    ./shiny-new-pc-test.sh
"

# ------------------------------------------------------------------------------
section "Running sanity checks"
# ------------------------------------------------------------------------------

CHECKS_PASSED=0
CHECKS_FAILED=0

check_command() {
    local cmd="$1"
    local desc="$2"
    if podman exec "${CONTAINER_NAME}" bash -c "command -v ${cmd}" &>/dev/null; then
        success "${desc}: ${cmd}"
        ((CHECKS_PASSED++))
    else
        fail "${desc}: ${cmd} not found"
        ((CHECKS_FAILED++))
    fi
}

check_command git "Version control"
check_command nvim "Editor"
check_command go "Go compiler"
check_command rustc "Rust compiler"
check_command cargo "Cargo"
check_command node "Node.js"
check_command uv "Python package manager"
check_command bun "Bun runtime"
check_command ruff "Python linter"
check_command tofu "OpenTofu"
check_command tflint "TFLint"
check_command conftest "Conftest"
check_command actionlint "GitHub Actions linter"
check_command delta "Git delta"
check_command difft "Difftastic"

# Check git configuration
section "Checking Git configuration"

if podman exec "${CONTAINER_NAME}" git config --global --get merge.conflictStyle | grep -q zdiff3; then
    success "Git merge.conflictStyle = zdiff3"
    ((CHECKS_PASSED++))
else
    fail "Git merge.conflictStyle not set correctly"
    ((CHECKS_FAILED++))
fi

if podman exec "${CONTAINER_NAME}" git config --global --get init.defaultBranch | grep -q main; then
    success "Git init.defaultBranch = main"
    ((CHECKS_PASSED++))
else
    fail "Git init.defaultBranch not set correctly"
    ((CHECKS_FAILED++))
fi

# Check PATH configuration
section "Checking PATH configuration"

if podman exec "${CONTAINER_NAME}" test -f /root/.bashrc.d/00-paths; then
    success "PATH configuration file exists"
    ((CHECKS_PASSED++))
else
    fail "PATH configuration file missing"
    ((CHECKS_FAILED++))
fi

# ------------------------------------------------------------------------------
section "Test Results"
# ------------------------------------------------------------------------------

echo
echo -e "Passed: ${GREEN}${CHECKS_PASSED}${NC}"
echo -e "Failed: ${RED}${CHECKS_FAILED}${NC}"
echo

if [[ ${CHECKS_FAILED} -eq 0 ]]; then
    success "All sanity checks passed!"
    cleanup_instructions
    exit 0
else
    fail "Some checks failed. Container preserved for debugging."
    cleanup_instructions
    exit 1
fi
