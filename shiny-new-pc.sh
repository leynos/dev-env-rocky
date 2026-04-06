#!/usr/bin/env bash
# shiny-new-pc.sh - Bootstrap a complete development environment
#
# This script orchestrates all the individual installers to set up a
# fully configured development environment from a fresh Fedora install.
#
# What gets installed:
#   - System packages (RPM): editors, compilers, languages, libraries
#   - Git configuration: sensible defaults, merge drivers, user identity
#   - PATH setup: ~/.local/bin, ~/.cargo/bin, ~/.bun/bin, ~/go/bin
#   - Rust tools: cargo-nextest, cross, mergiraf, etc.
#   - Python tools: ruff, pyrefly, yamllint, copier, etc.
#   - Node tools: biome, pnpm, mermaid-cli, claude-code, etc.
#   - Go tools: actionlint, checkmake
#   - Infrastructure tools: OpenTofu, TFLint, Conftest
#
# Usage:
#     ./shiny-new-pc.sh
#
# Exit codes:
#     0  All installations completed successfully
#     *  Exit code from failed installer
#
# Note:
#     Some installers require sudo and will prompt for password.
#     Git setup will prompt for your name and email.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${SCRIPT_DIR}/bin"

# Colours for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No colour

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

warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# ------------------------------------------------------------------------------
section "Installing system packages (RPM)"
# ------------------------------------------------------------------------------

if [[ -f "${SCRIPT_DIR}/rpm-packages.inf" ]]; then
    "${BIN_DIR}/install-packages" "${SCRIPT_DIR}/rpm-packages.inf"
    success "System packages installed"
else
    warn "rpm-packages.inf not found, skipping"
fi

# ------------------------------------------------------------------------------
section "Configuring Git"
# ------------------------------------------------------------------------------

"${BIN_DIR}/git-setup"
success "Git configured"

# ------------------------------------------------------------------------------
section "Installing Python tools (uv)"
# ------------------------------------------------------------------------------

if [[ -f "${SCRIPT_DIR}/uv-tools.inf" ]]; then
    "${BIN_DIR}/install-uv-tools" "${SCRIPT_DIR}/uv-tools.inf"
    success "Python tools installed"
else
    warn "uv-tools.inf not found, skipping"
fi

# ------------------------------------------------------------------------------
section "Setting up PATH"
# ------------------------------------------------------------------------------

"${HOME}/.local/bin/uv" run --script "${BIN_DIR}/setup-paths"
success "PATH configuration written to ~/.bashrc.d/00-paths"

# Source the new PATH for this session
if [[ -f "${HOME}/.bashrc.d/00-paths" ]]; then
    # shellcheck source=/dev/null
    source "${HOME}/.bashrc.d/00-paths"
fi

# ------------------------------------------------------------------------------
section "Installing Rust crates"
# ------------------------------------------------------------------------------

if [[ -f "${SCRIPT_DIR}/crates.inf" ]]; then
    "${BIN_DIR}/install-crates" "${SCRIPT_DIR}/crates.inf"
    success "Rust crates installed"
else
    warn "crates.inf not found, skipping"
fi

# ------------------------------------------------------------------------------
section "Installing Node packages (bun)"
# ------------------------------------------------------------------------------

if [[ -f "${SCRIPT_DIR}/bun-packages.inf" ]]; then
    "${BIN_DIR}/install-bun-packages" "${SCRIPT_DIR}/bun-packages.inf"
    success "Node packages installed"
else
    warn "bun-packages.inf not found, skipping"
fi

# ------------------------------------------------------------------------------
section "Installing Go packages"
# ------------------------------------------------------------------------------

if [[ -f "${SCRIPT_DIR}/go-packages.inf" ]]; then
    "${BIN_DIR}/install-go-packages" "${SCRIPT_DIR}/go-packages.inf"
    success "Go packages installed"
else
    warn "go-packages.inf not found, skipping"
fi

# ------------------------------------------------------------------------------
section "Installing infrastructure tools"
# ------------------------------------------------------------------------------

"${BIN_DIR}/install-opentofu"
"${BIN_DIR}/install-tflint"
"${BIN_DIR}/install-conftest"
success "Infrastructure tools installed"

# ------------------------------------------------------------------------------
section "Setup complete!"
# ------------------------------------------------------------------------------

echo "Your shiny new PC is ready for action."
echo
echo "You may need to restart your shell or run:"
echo "    source ~/.bashrc"
echo
echo "To verify installations, try:"
echo "    git --version"
echo "    rustc --version"
echo "    go version"
echo "    node --version"
echo "    uv --version"
echo "    bun --version"
echo "    tofu --version"
