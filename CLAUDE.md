# Claude Code Development Guide for pyvector-rs

## Project Overview
pyvector-rs is a Python extension written in Rust that integrates Vector data processing pipelines with Python applications. It uses PyO3 for Python bindings and maturin for building. Licensed under Apache-2.0.

## Quick Start

### Prerequisites
First, install system dependencies by running the bootstrap script:

```bash
# Install system dependencies for your platform (Fedora/RHEL, Ubuntu/Debian, or macOS)
./scripts/bootstrap.sh
```

This script will:
- Install Rust and uv if not present
- Install required system packages (OpenSSL, protobuf, build tools, etc.)
- Set up a local Python virtual environment
- Install Python development dependencies

### Build and Development
```bash
# Build and install in development mode (with all compatibility flags)
RUSTFLAGS="-C linker=gcc" PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 uv run maturin develop

# Simplified build for subsequent builds (once environment is working)  
uv run maturin develop

# Skip auto-version detection for faster development builds
SKIP_VECTOR_UPDATE=1 RUSTFLAGS="-C linker=gcc" PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 uv run maturin develop

# Build release version
uv run maturin build --release
```

### Dependency Management

This project uses flexible version constraints (`>=X.Y.Z`) to automatically use the latest compatible versions:

```bash
# Update all dependencies to their latest compatible versions
./scripts/update-deps.sh

# Update to latest available versions (may include breaking changes)
./scripts/update-deps.sh --all

# Skip compatibility testing (faster but less safe)
./scripts/update-deps.sh --skip-test
```

The build system automatically:
- Detects and uses the latest compatible Vector version
- Updates other dependencies when `UPDATE_DEPENDENCIES=1` is set
- Falls back to known-good versions if latest versions have issues

### Environment Variables
- `RUSTFLAGS="-C linker=gcc"` - Use GCC as linker (avoids mold/ld issues)
- `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` - Allow PyO3 to work with newer Python versions
- `SKIP_VECTOR_UPDATE=1` - Skip automatic Vector version detection for faster builds
- `UPDATE_DEPENDENCIES=1` - Update all dependencies to latest compatible versions at build time
- `OPENSSL_NO_VENDOR=1` - Use system OpenSSL instead of vendored version (if needed)

### Testing
```bash
# Run Python tests
uv run pytest tests/

# Run specific test
uv run pytest tests/test_basic.py -v

# Run example
uv run python example.py
```

### Linting and Formatting
```bash
# Rust formatting
cargo fmt

# Rust linting
cargo clippy

# Python formatting (with ruff in venv)
uv run ruff format tests/ example.py

# Python linting (with ruff in venv)
uv run ruff check tests/ example.py
```

## Project Structure
- `src/lib.rs` - Main Python module entry point and Vector class
- `src/vector_app.rs` - Vector application lifecycle management
- `src/python_source.rs` - Custom Python source implementation for Vector
- `src/vector_context.rs` - Global Vector runtime context
- `tests/` - Python test files
- `example.py` - Usage example
- `Cargo.toml` - Rust dependencies and configuration (auto-updates Vector version)
- `pyproject.toml` - Python package configuration
- `build.rs` - Build script for automatic Vector version detection
- `scripts/update-deps.sh` - Comprehensive dependency update management
- `LICENSE` - HyperSec EULA license

## Dependencies
- **Rust**: PyO3 for Python bindings, Vector for data processing (auto-updated to latest release)
- **Python**: asyncio for async support, pytest for testing
- **Build**: maturin for building Python wheels

## Automatic Vector Updates
The project automatically uses the latest Vector release:
- Build script (`build.rs`) fetches the latest Vector version from GitHub API
- Cargo.toml is updated automatically during build
- Features are set to use the new Vector feature system: `transforms-logs`, `transforms-metrics`, `sinks-logs`, `sinks-metrics`
- Use `SKIP_VECTOR_UPDATE=1` environment variable to skip version updates for faster rebuilds

## Common Development Tasks
1. **Adding new Vector features**: Vector features auto-detected via build system 
2. **Testing changes**: Use `maturin develop` then run Python tests
3. **Performance testing**: Use example.py with large data sets
4. **Manual dependency update**: Run `./scripts/update-deps.sh` for latest versions
5. **CI/CD**: GitHub Actions in `.github/workflows/ci.yaml`