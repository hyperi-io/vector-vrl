#!/bin/bash

# Script to update all dependencies to their latest compatible versions
# This script provides a safe way to keep dependencies up-to-date

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

# Backup current Cargo.lock
backup_lockfile() {
    if [[ -f "Cargo.lock" ]]; then
        cp Cargo.lock Cargo.lock.backup
        log_info "Backed up Cargo.lock to Cargo.lock.backup"
    fi
}

# Restore Cargo.lock from backup
restore_lockfile() {
    if [[ -f "Cargo.lock.backup" ]]; then
        mv Cargo.lock.backup Cargo.lock
        log_info "Restored Cargo.lock from backup"
    fi
}

# Update Rust dependencies
update_rust_deps() {
    log_info "Updating Rust dependencies..."
    
    # Always update to latest compatible versions
    cargo update 2>/dev/null || {
        log_error "Failed to update Rust dependencies"
        return 1
    }
    
    # If UPDATE_ALL is set, also trigger build-time dependency updates including Vector
    if [[ "${UPDATE_ALL:-}" == "1" ]]; then
        log_info "Triggering full dependency update including latest Vector version..."
        UPDATE_DEPENDENCIES=1 cargo check --quiet 2>/dev/null || {
            log_warning "Full dependency update encountered issues, will use current lock file versions"
            return 1
        }
    else
        log_info "Vector version will be auto-detected at next build (always uses latest stable)"
    fi
    
    log_success "Rust dependencies updated successfully"
}

# Update Python dependencies
update_python_deps() {
    log_info "Updating Python dependencies in virtual environment..."
    
    if [[ ! -d ".venv" ]]; then
        log_warning "No virtual environment found, creating one..."
        uv venv .venv
    fi
    
    # Update to latest versions
    uv pip install --upgrade maturin pytest ruff 2>/dev/null || {
        log_error "Failed to update Python dependencies"
        return 1
    }
    
    log_success "Python dependencies updated successfully"
}

# Check for outdated Rust crates
check_outdated() {
    log_info "Checking for outdated dependencies..."
    
    # Install cargo-outdated if not available
    if ! command -v cargo-outdated &> /dev/null; then
        log_info "Installing cargo-outdated..."
        cargo install cargo-outdated 2>/dev/null || {
            log_warning "Could not install cargo-outdated, skipping outdated check"
            return 0
        }
    fi
    
    # Check for outdated dependencies
    if cargo outdated --exit-code 1 2>/dev/null; then
        log_info "All Rust dependencies are up to date"
    else
        log_warning "Some Rust dependencies have newer versions available"
        log_info "Run 'cargo outdated' for details"
    fi
}

# Test that dependencies work together
test_deps() {
    log_info "Testing updated dependencies..."
    
    # Test Rust compilation
    if ! cargo check --quiet 2>/dev/null; then
        log_error "Updated Rust dependencies failed to compile"
        return 1
    fi
    
    # Test Python environment
    if ! uv run python -c "import maturin, pytest, ruff" 2>/dev/null; then
        log_error "Updated Python dependencies have issues"
        return 1
    fi
    
    log_success "All updated dependencies work correctly"
}

# Main function
main() {
    log_info "Starting dependency update process"
    
    # Parse command line arguments
    UPDATE_ALL=0
    SKIP_TEST=0
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)
                UPDATE_ALL=1
                shift
                ;;
            --skip-test)
                SKIP_TEST=1
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --all         Update to latest available versions (may include breaking changes)"
                echo "  --skip-test   Skip dependency compatibility testing"
                echo "  --help        Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Create backup
    backup_lockfile
    
    # Update dependencies
    if ! update_rust_deps; then
        log_error "Rust dependency update failed, restoring backup"
        restore_lockfile
        exit 1
    fi
    
    if ! update_python_deps; then
        log_error "Python dependency update failed"
        exit 1
    fi
    
    # Test dependencies unless skipped
    if [[ $SKIP_TEST -eq 0 ]]; then
        if ! test_deps; then
            log_error "Dependency testing failed, restoring backup"
            restore_lockfile
            exit 1
        fi
    fi
    
    # Check for further updates
    check_outdated
    
    # Clean up backup on success
    if [[ -f "Cargo.lock.backup" ]]; then
        rm Cargo.lock.backup
    fi
    
    log_success "Dependency update completed successfully!"
    log_info "Run 'uv run maturin develop' to rebuild with updated dependencies"
    
    if [[ $UPDATE_ALL -eq 1 ]]; then
        log_warning "Full update was performed - please test thoroughly before committing"
    fi
}

# Run main function
main "$@"