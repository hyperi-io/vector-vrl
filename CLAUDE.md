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

#### Smart Auto-Fallback Build (Recommended)
```bash
# Intelligent build with automatic Vector version detection and fallback
./scripts/smart-build.sh

# For CI/CD environments with additional options
BUILD_FORCE_UPDATE=1 RUN_TESTS=1 ./scripts/ci-build.sh
```

The smart build system:
- 🔍 **Auto-detects** the latest compatible Vector version
- 🔄 **Progressive fallback** through up to 3 previous versions if issues found
- 🧠 **Distinguishes** between upstream Vector incompatibilities vs code issues
- ✅ **Full verification** including module import testing
- 🤖 **CI/CD ready** with GitHub Actions integration

#### Manual Build (Advanced Users)
```bash
# Build and install in development mode (with all compatibility flags)
RUSTFLAGS="-C linker=gcc" PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 uv run maturin develop

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

## Smart Vector Version Management

### Automatic Updates with Fallback
The project uses an intelligent build system that:
- 🔍 **Auto-detects** the latest stable Vector version via GitHub API
- 🔄 **Progressive fallback** if latest version has compatibility issues
- 🧠 **Smart error detection** distinguishes upstream vs code problems
- ✅ **Full verification** ensures working builds

### Upstream Issue Detection
Automatically detects and handles:
- Vector/VRL protobuf API changes (`proto_to_value`, `get_message_descriptor`, etc.)
- Dependency version conflicts (`indexmap`, etc.)  
- Compilation errors in Vector's `codecs` library
- System library issues (`krb5`, `gssrpc`, etc.)

### CI/CD Integration
- GitHub Actions workflow with daily version checks
- Automatic fallback on build failures
- Build artifact management and releases
- Notifications for persistent failures

Use `SKIP_VECTOR_UPDATE=1` environment variable to skip version updates for faster rebuilds.

## Common Development Tasks
1. **Adding new Vector features**: Vector features auto-detected via build system 
2. **Testing changes**: Use `maturin develop` then run Python tests
3. **Performance testing**: Use example.py with large data sets
4. **Manual dependency update**: Run `./scripts/update-deps.sh` for latest versions
5. **CI/CD**: GitHub Actions in `.github/workflows/ci.yaml`

## Emoji Policy

**Context-Specific Usage:** Documentation/UI/Console: All approved emojis permitted. Log Files/Machine-Parsed: ASCII only.

**Professional Emojis:**
:white_tick::x::warning::information_source::red_circle::large_yellow_circle::large_green_circle::large_blue_circle::arrow_right::arrow_left::arrow_up::arrow_down::arrow_upper_right::arrow_lower_right:✓✗:ballot_box_with_tick:☐:closed_lock_with_key::no_entry_symbol:🛇:no_entry::double_vertical_bar::black_square_for_stop::hourglass_flowing_sand::insect::spanner::cog::hammer_and_spanner::hammer::green_heart::siren::builder::recycle::rocket::sparkles::arrows_anticlockwise::twisted_rightwards_arrows::arrows_clockwise::repeat::leftwards_arrow_with_hook::arrow_right_hook::dart::arrow_forwards::zap::magnifying_glass::magnifying_glass_right::computer::desktop_computer::globe_with_meridians::robot_face:●○◆◇■□▲△▼▽→←↑↓:left_right_arrow::arrow_up_down:±×÷∞≈≠≤≥№§¶©®™

**ASCII:** ─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬╭╮╯╰▁▂▃▄▅▆▇█░▒▓

**Log ASCII:** [OK][FAIL][WARN][INFO][CRIT][DBG][OFF][BLOCK][DENY][PROC][PAUSE][STOP]

**Key Updates Made** ✓
1. Context-Specific Rules: Clear separation between documentation vs logs
2. Expanded Professional Set: Added Categories A, B, D, E + search icons + extended Unicode  
3. ASCII Log Alternatives: Standardized bracket codes for machine-parsed content
4. Comprehensive Coverage: 50+ professional emojis + full ASCII line drawing + log safety

## Temporary File Policy

**CORPORATE REQUIREMENT**: Never use system locations for temporary files:

- ❌ **Forbidden**: `/tmp`, `~/`, system temp directories for Claude Code or build processes
- ✅ **Required**: Use project-relative path `./.tmp/` for all temporary files
- 🗂️ **Structure**: Create `.tmp/` directory in project root for all build artifacts, logs, caches  
- 🧹 **Cleanup**: Include `.tmp/` in `.gitignore` and ensure automatic cleanup
- ⚙️ **Configuration**: Temp file location must be configurable via environment variable or config file

**Environment Variable**: `PYVECTOR_TEMP_DIR` (defaults to `./.tmp/`)

**For Projects**: Ensure temp file location is a config or ENV setting, never hardcoded.

**Rationale**: Ensures build reproducibility, avoids permission issues, keeps all artifacts contained within project scope, meets corporate security requirements.

## Configuration Policy

**Never hardcode values. Use dynaconf for Python.**

**Precedence**: CLI → ENV → .env → config file → code default

**Setup:**
```python
from dynaconf import Dynaconf
settings = Dynaconf(envvar_prefix="APP", settings_files=['settings.toml'], load_dotenv=True)
```

**Deployment**: Deploy to K8s/Helm. ENV vars use `APP_` prefix.

**Implementation Requirements:**
- ✅ All configurable values must support environment variables
- ✅ Use `PYVECTOR_` prefix for environment variables
- ✅ Support `.env` files for local development
- ✅ Provide sensible defaults in code
- ✅ CLI arguments override all other sources

## Git LFS and CI/CD Caching

### LFS Setup for Build Optimization
```bash
# One-time setup
bash build/setup-lfs.sh
git add .gitattributes
git commit -m "Add Git LFS configuration for build caching"

# Enable caching  
export PYVECTOR_USE_CACHE=true
./smart-build
```

### Cached Build Artifacts
**Large Files (LFS-tracked):**
- `target/release/deps/*.rlib` - Rust compiled libraries
- `target/wheels/*.whl` - Python wheels
- `.tmp/build-cache-*.tar.gz` - Compressed build caches
- `.tmp/build_vector_*.log` - Build logs for analysis
- `**/*.so`, `**/*.dylib`, `**/*.a` - Compiled dependencies

**Excluded Files:**
- Debug artifacts (`target/debug/`)
- Temporary files (`.tmp/*.tmp`)
- IDE files (`.idea/`, `.vscode/`)
- Environment files (`.env*`)
- System caches (`.DS_Store`, `Thumbs.db`)

### CI/CD Integration Features
- **Git LFS auto-pull** for cached dependencies
- **Smart cache keys** based on Cargo.toml + config changes
- **Cache restoration** before builds for faster compilation
- **Automatic cache creation** on successful builds
- **Cache cleanup** with configurable retention
- **GitHub Actions optimization** with LFS-aware caching

### Cache Management
```bash
# Manual cache operations
build/.venv/bin/python build/lfs_cache_manager.py --list-caches
build/.venv/bin/python build/lfs_cache_manager.py --cleanup
build/.venv/bin/python build/lfs_cache_manager.py --restore-cache v0.48.0
```