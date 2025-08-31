#!/bin/bash

# Comprehensive test runner for pyvector-rs
# Supports different test categories and environments

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

# Help function
show_help() {
    cat << EOF
Test runner for pyvector-rs

Usage: $0 [OPTIONS] [TEST_PATTERN]

Options:
    --all           Run all tests including slow ones
    --fast          Run only fast tests (excludes performance tests)
    --performance   Run only performance tests
    --integration   Run only integration tests
    --unit          Run only unit tests
    --coverage      Run tests with coverage reporting
    --verbose       Verbose test output
    --help          Show this help message

Examples:
    $0                          # Run default test suite
    $0 --fast                   # Quick test run
    $0 --performance           # Performance tests only
    $0 --coverage              # Run with coverage
    $0 test_basic.py           # Run specific test file
    $0 --verbose test_data_    # Run data processing tests verbosely

EOF
}

# Parse command line arguments
COVERAGE=0
VERBOSE=0
TEST_MARKERS=""
TEST_PATTERN=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            TEST_MARKERS=""
            shift
            ;;
        --fast)
            TEST_MARKERS='-m "not slow and not performance"'
            shift
            ;;
        --performance)
            TEST_MARKERS='-m performance'
            shift
            ;;
        --integration)
            TEST_MARKERS='-m integration'
            shift
            ;;
        --unit)
            TEST_MARKERS='-m "not integration and not performance"'
            shift
            ;;
        --coverage)
            COVERAGE=1
            shift
            ;;
        --verbose)
            VERBOSE=1
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            TEST_PATTERN="$1"
            shift
            ;;
    esac
done

# Main test function
run_tests() {
    log_info "Starting pyvector-rs test suite"
    
    # Check if virtual environment exists
    if [[ ! -d ".venv" ]]; then
        log_warning "No virtual environment found, creating one..."
        uv venv .venv
        uv pip install pytest pytest-asyncio ruff
    fi
    
    # Build test command
    local cmd="uv run pytest tests/"
    
    if [[ -n "$TEST_PATTERN" ]]; then
        cmd="$cmd -k $TEST_PATTERN"
    fi
    
    if [[ -n "$TEST_MARKERS" ]]; then
        cmd="$cmd $TEST_MARKERS"
    fi
    
    if [[ $COVERAGE -eq 1 ]]; then
        # Install coverage if not available
        uv pip install pytest-cov 2>/dev/null || true
        cmd="$cmd --cov=pyvector --cov-report=html --cov-report=term"
    fi
    
    if [[ $VERBOSE -eq 1 ]]; then
        cmd="$cmd -v -s"
    fi
    
    log_info "Running: $cmd"
    
    # Run tests
    if eval "$cmd"; then
        log_success "All tests passed!"
        
        if [[ $COVERAGE -eq 1 ]]; then
            log_info "Coverage report generated in htmlcov/"
        fi
        
        return 0
    else
        log_error "Some tests failed"
        return 1
    fi
}

# Check prerequisites
check_prerequisites() {
    local errors=0
    
    # Check essential tools
    for tool in uv; do
        if ! command -v $tool &> /dev/null; then
            log_error "$tool is not installed. Run ./scripts/bootstrap.sh first."
            errors=$((errors + 1))
        fi
    done
    
    if [[ $errors -gt 0 ]]; then
        log_error "Missing prerequisites. Please run ./scripts/bootstrap.sh first."
        exit 1
    fi
}

# Lint check
run_lint() {
    log_info "Running Python linting..."
    
    if uv run ruff check tests/ example.py 2>/dev/null; then
        log_success "Python linting passed"
    else
        log_warning "Python linting found issues (non-blocking)"
    fi
    
    log_info "Running Rust linting..."
    if cargo clippy --all-targets -- -D warnings 2>/dev/null; then
        log_success "Rust linting passed"
    else
        log_warning "Rust linting found issues (non-blocking)"
    fi
}

# Main execution
main() {
    check_prerequisites
    
    # Run linting first
    run_lint
    
    # Run the tests
    if run_tests; then
        log_success "Test run completed successfully!"
        exit 0
    else
        log_error "Test run failed"
        exit 1
    fi
}

# Run main function
main "$@"