# Claude Code Development Guide for vectordotdev

## Project Overview
vectordotdev is a Python extension written in Rust that integrates Vector data processing pipelines with Python applications. It uses PyO3 for Python bindings and maturin for building. Licensed under Apache-2.0.

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

### Clear Language Separation
```
/src/                    # Python code ONLY
├── build_system/        # Python build automation
├── tests/              # Python test suite  
├── examples/           # Python usage examples
└── pyproject.toml     # Python dependencies

/vector/                # Vector/Rust code ONLY  
├── lib.rs             # PyO3 bindings entry point
├── vector_app.rs      # Vector application lifecycle
├── python_source.rs   # Python-Vector bridge
├── vector_cli.rs      # CLI compatibility layer
├── vector_context.rs  # Global Vector runtime
└── vrl_checker.rs     # VRL syntax validation

/build/                 # Build configuration
├── build.rs           # Rust build script
└── workflows/         # CI/CD automation
```

### Linting and Formatting Scope
- **Python linting**: Only applies to `/src/` directory
- **Rust formatting**: Manual only for `/vector/` directory  
- **VS Code**: Configured to respect language boundaries

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

**Environment Variable**: `VECTORDOTDEV_TEMP_DIR` (defaults to `./.tmp/`)

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
- ✅ Use `VECTORDOTDEV_` prefix for environment variables
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

## Current Build System Status

### 3-Stage Build Architecture ✅
**Complete modular build system with intelligent monitoring and auto-remediation:**

```bash
# Primary build entry point
build/.venv/bin/python build/build_system.py

# Test build flow without full Vector compilation  
build/.venv/bin/python build/build_system.py --test-flow

# Test stages 2-3 only (requires existing Vector build)
build/.venv/bin/python build/build_system.py --skip-vector
```

### Stage Status Summary
- **Stage 1 (Vector Core)**: ✅ Working with auto-detection and fallback
- **Stage 2 (Vector Bindings)**: ✅ Working with dependency sync (2.0s build)
- **Stage 3 (Python Layer)**: ⚠️ Needs investigation - failing during maturin develop

### Modular Components ✅
Split from 850+ line monolith into focused modules:

| Module | Purpose | Status |
|--------|---------|--------|
| `build_system.py` | Main orchestrator with CLI | ✅ Working |
| `core_build.py` | 3-stage build execution | ✅ Working |
| `vector_detection.py` | Auto-detection and version management | ✅ Working |
| `dependency_sync.py` | Vector → bindings dependency sync | ✅ Working |
| `monitoring.py` | Intelligent build monitoring | ✅ Working |
| `common.py` | Shared types and utilities | ✅ Working |

### Key Features Working ✅
- **Vector Auto-Detection**: "Found existing Vector 0.49.0 build (0.3h old, 20 artifacts)"
- **Dependency Synchronization**: "Synced 8 dependencies with Vector v0.49.0"
- **Intelligent Monitoring**: File growth + phase detection (no simple timeouts)
- **Progressive Fallback**: v0.49.0 → v0.48.0 → v0.47.0 on upstream failures
- **Git Metadata Cleanup**: Complete removal of .git* from /vector
- **Auto-Remediation**: Automatic dependency fixes during build

### Recent Fixes ✅
- ✅ Fixed StageResult artifacts parameter error
- ✅ Fixed serde_json std feature requirement 
- ✅ Fixed tar extraction Python 3.14 compatibility
- ✅ Fixed git 10K+ changes with comprehensive .gitignore
- ✅ Disabled GitHub CI/CD automation (no email spam)
- ✅ Implemented generous timeouts (30min compiling, 15min downloading)

### Next Investigation Required
**Stage 3 Python Layer Failure**: While vector-bindings (Stage 2) now builds successfully in 2.0s, the Python layer still fails during `uv run maturin develop`. Investigation needed in `.tmp/python_*.log` files to identify specific compilation errors and implement auto-remediation.