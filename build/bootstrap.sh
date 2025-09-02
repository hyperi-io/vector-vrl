#!/bin/bash

# Bootstrap script to install pyvector-rs development dependencies
# Supports Fedora/RHEL, Ubuntu/Debian, and macOS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect operating system
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ -f /etc/fedora-release ]] || [[ -f /etc/redhat-release ]] || [[ -f /etc/centos-release ]]; then
        OS="fedora"
    elif [[ -f /etc/debian_version ]] || [[ -f /etc/ubuntu-release ]]; then
        OS="debian"
    else
        log_error "Unsupported operating system. This script supports Fedora/RHEL, Ubuntu/Debian, and macOS."
        exit 1
    fi
    
    log_info "Detected operating system: $OS"
}

# Install Rust if not present
install_rust() {
    if ! command -v rustc &> /dev/null; then
        log_info "Installing Rust..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
        log_success "Rust installed successfully"
    else
        log_info "Rust is already installed"
    fi
}

# Install uv if not present
install_uv() {
    if ! command -v uv &> /dev/null; then
        log_info "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        log_success "uv installed successfully"
    else
        log_info "uv is already installed"
    fi
}

# Install system dependencies for Fedora/RHEL
install_fedora_deps() {
    log_info "Installing Fedora/RHEL dependencies..."
    
    local packages=(
        "gcc"
        "gcc-c++"
        "make"
        "cmake"
        "pkg-config"
        "openssl-devel"
        "libffi-devel"
        "python3-devel"
        "perl-FindBin"
        "perl-IPC-Cmd"
        "binutils"
        "binutils-devel"
        "kernel-headers"
        "glibc-devel"
        "libstdc++-devel"
        "clang"
        "llvm-devel"
        "zlib-devel"
        "xz-devel"
        "lz4-devel"
        "libzstd-devel"
        "protobuf-compiler"
        "protobuf-devel"
    )
    
    # Check if we have dnf or yum
    if command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
    else
        log_error "Neither dnf nor yum found"
        exit 1
    fi
    
    log_info "Using package manager: $PKG_MANAGER"
    sudo $PKG_MANAGER install -y "${packages[@]}"
    
    log_success "Fedora/RHEL dependencies installed successfully"
}

# Install system dependencies for Ubuntu/Debian
install_debian_deps() {
    log_info "Installing Ubuntu/Debian dependencies..."
    
    local packages=(
        "build-essential"
        "cmake"
        "pkg-config"
        "libssl-dev"
        "libffi-dev"
        "python3-dev"
        "perl"
        "binutils-dev"
        "curl"
        "git"
    )
    
    sudo apt-get update
    sudo apt-get install -y "${packages[@]}"
    
    log_success "Ubuntu/Debian dependencies installed successfully"
}

# Install system dependencies for macOS
install_macos_deps() {
    log_info "Installing macOS dependencies..."
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        log_info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    else
        log_info "Homebrew is already installed"
    fi
    
    local packages=(
        "cmake"
        "pkg-config"
        "openssl"
        "libffi"
    )
    
    brew install "${packages[@]}"
    
    # Set environment variables for OpenSSL on macOS
    if [[ -d "/opt/homebrew/opt/openssl" ]]; then
        # Apple Silicon Macs
        OPENSSL_DIR="/opt/homebrew/opt/openssl"
    elif [[ -d "/usr/local/opt/openssl" ]]; then
        # Intel Macs
        OPENSSL_DIR="/usr/local/opt/openssl"
    fi
    
    if [[ -n "$OPENSSL_DIR" ]]; then
        log_info "Setting OpenSSL environment variables for macOS"
        echo "export OPENSSL_DIR=\"$OPENSSL_DIR\"" >> ~/.zshrc || true
        echo "export PKG_CONFIG_PATH=\"$OPENSSL_DIR/lib/pkgconfig:\$PKG_CONFIG_PATH\"" >> ~/.zshrc || true
        export OPENSSL_DIR="$OPENSSL_DIR"
        export PKG_CONFIG_PATH="$OPENSSL_DIR/lib/pkgconfig:$PKG_CONFIG_PATH"
    fi
    
    log_success "macOS dependencies installed successfully"
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."
    
    local errors=0
    
    # Check essential tools
    for tool in gcc rustc uv; do
        if ! command -v $tool &> /dev/null; then
            log_error "$tool is not installed or not in PATH"
            errors=$((errors + 1))
        else
            log_info "$tool is available"
        fi
    done
    
    # Check pkg-config can find OpenSSL
    if pkg-config --exists openssl; then
        log_info "OpenSSL development libraries found via pkg-config"
    else
        log_warning "OpenSSL development libraries not found via pkg-config"
        log_info "This might be resolved by setting OPENSSL_DIR environment variable"
        if [[ "$OS" == "macos" ]]; then
            log_info "For macOS, make sure to restart your terminal or source ~/.zshrc"
        fi
    fi
    
    if [[ $errors -eq 0 ]]; then
        log_success "All essential dependencies verified successfully"
    else
        log_error "$errors essential dependencies are missing"
        exit 1
    fi
}

# Setup local development environment
setup_dev_env() {
    log_info "Setting up local development environment..."
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d ".venv" ]]; then
        uv venv .venv
        log_success "Created Python virtual environment"
    else
        log_info "Python virtual environment already exists"
    fi
    
    # Install Python dependencies
    log_info "Installing Python dependencies..."
    uv pip install maturin pytest ruff
    
    log_success "Development environment setup complete"
}

# Main function
main() {
    log_info "Starting pyvector-rs development environment bootstrap"
    
    detect_os
    install_rust
    install_uv
    
    case $OS in
        "fedora")
            install_fedora_deps
            ;;
        "debian")
            install_debian_deps
            ;;
        "macos")
            install_macos_deps
            ;;
    esac
    
    verify_installation
    setup_dev_env
    
    log_success "Bootstrap completed successfully!"
    log_info "You can now run: uv run maturin develop"
    
    if [[ "$OS" == "macos" ]]; then
        log_info "On macOS, you may need to restart your terminal or run: source ~/.zshrc"
    fi
}

# Run main function
main "$@"