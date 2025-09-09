# Claude Code Development Guide for vectordotdev

## Project Overview
vectordotdev is a Python extension written in Rust that provides **native in-app Vector execution** for Python applications. The core purpose is to enable Python projects to execute Vector data processing pipelines directly in-process using supplied YAML/TOML configurations, eliminating the need for command-line subprocess calls.

### Core Purpose & Goals
**PRIMARY GOAL**: Native in-app Vector execution via PyO3 bindings
- **No subprocess calls**: Direct Vector runtime integration in Python process
- **YAML/TOML config support**: Supply Vector configurations as dictionaries or files
- **Native error handling**: Collect and trap Vector/VRL errors programmatically without parsing text output
- **THG benchmarking**: Consistent performance scoring against supplied test data for optimization
- **Embeddable**: Works in any Python application without external Vector binary dependency

**EXECUTION MODEL**:
```python
import vectordotdev

# Configure Vector pipeline with YAML/TOML (no external files)
config = {
    "sources": {"logs": {"type": "file", "include": ["*.log"]}},
    "transforms": {"parse": {"type": "remap", "source": "VRL_CODE_HERE"}}, 
    "sinks": {"output": {"type": "console", "encoding": {"codec": "json"}}}
}

# Execute Vector pipeline in-process (no subprocess)
vector = vectordotdev.Vector(config)
vector.initialize()                           # Native initialization
results = vector.process_logs(input_logs)     # In-memory processing
stats = vector.get_stats()                    # Native metrics collection

# THG performance assessment
thg_result = vectordotdev.assess_vrl_performance(vrl_code, test_logs)
print(f"THG Score: {thg_result['thg_score']} Grade: {thg_result['performance_grade']}")
```

**BENEFITS vs Command-line Vector**:
- **10x+ Performance**: No subprocess/IPC overhead
- **Memory Efficiency**: Shared memory, no external process
- **Error Handling**: Native Python exceptions instead of text parsing
- **Programmatic Control**: Full Python integration and automation
- **Deployment**: Single PyPI package, no external dependencies

### **Implementation Status (v1.0.1)**
#### **✅ PHASE 1: Build System & THG Framework (COMPLETE)**
- **3-stage build system**: Vector → Bindings → Python → JFrog PyPI
- **THG assessment framework**: Performance scoring, benchmarking, optimization recommendations
- **GCC 15+ compatibility**: Auto-fix system for build environment issues
- **Git safety**: Zero build artifact pollution
- **JFrog deployment**: Verified working to Artifactory PyPI

#### **⚠️ PHASE 2: Native Vector Integration (IN PROGRESS)**
- **PyO3 bindings structure**: Created for in-process Vector execution
- **API design**: Vector class, execute_vrl(), native error handling designed
- **Vector core integration**: Needs Vector runtime API binding (next step)
- **VRL engine access**: Direct VRL transform execution (next step)

#### **🎯 TARGET API (Final Goal)**:
```python
# Native in-process Vector execution (no subprocess)
import vectordotdev

vector = vectordotdev.Vector(yaml_config)    # YAML/TOML → Vector runtime
vector.initialize()                          # Native Vector initialization  
results = vector.process_logs(input_data)    # In-memory processing
errors = vector.get_errors()                 # Native error collection
thg = vectordotdev.assess_vrl_performance(vrl, test_data)  # THG benchmarking
```

### **Production Pattern Library**
vectordotdev includes **pre-provisioned production patterns** for common log formats with native execution and THG optimization:

#### **✅ Supported Production Patterns (v1.0.1)**
- **Apache Combined Logs**: HTTP access logs with full field extraction (10 fields)
- **Nginx Access Logs**: Web server logs with performance optimization (9 fields)
- **Docker Container Logs**: Container runtime logs with structured parsing (4 fields)
- **Kubernetes Pod Logs**: K8s orchestration logs with namespace extraction (4 fields)
- **JSON Application Logs**: Structured application logs with built-in parsers
- **Syslog Standard**: System logs with RFC3164/RFC5424 support
- **AWS ELB Logs**: Load balancer logs with complex multi-field parsing
- **MySQL Error Logs**: Database logs with error categorization

#### **Pattern Usage with Native Execution**
```python
# Use production patterns with native Vector execution
from vectordotdev import production_patterns

# Get pre-optimized Apache pattern (350+ THG score)
apache_config = production_patterns.get_apache_combined()
vector = vectordotdev.Vector(apache_config)
vector.initialize()

# Process Apache logs natively in-process
apache_logs = [
    '192.168.1.1 - user [08/Sep/2023:12:00:00 +0000] "GET /api HTTP/1.1" 200 1234'
]
results = vector.process_logs(apache_logs)  # Native parsing, no subprocess

# THG assessment of production pattern
thg = vectordotdev.assess_pattern_performance("apache_combined", apache_logs)
print(f"Production pattern THG: {thg['thg_score']} ({thg['performance_grade']})")
```

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
# Run all vectordotdev tests (unit, integration, e2e)
cd vectordotdev/tests && python run_tests.py

# Run unit tests only (Vector subprocess calls - no mocks)
python run_tests.py --category unit --verbose

# Run integration tests only (vectordotdev bindings)  
python run_tests.py --category integration --verbose

# Run individual test categories directly
cd vectordotdev/tests
python unit/test_regex2vrl_subprocess.py --verbose        # Unit tests (subprocess)
python integration/bindings.py --verbose                 # Integration tests (bindings)
python e2e/production_patterns.py --verbose              # E2E tests (full patterns)

# Legacy tests
uv run pytest tests/ -v                                  # Original pytest tests
uv run python example.py                                 # Basic example
```

### Test Structure
```
vectordotdev/tests/
├── run_tests.py              # Main test runner
├── unit/                     # Unit tests (isolated, subprocess Vector)
│   ├── test_regex2vrl_subprocess.py  # regex2vrl → Vector subprocess
│   └── test_vrl_*.py         # VRL function tests
├── integration/              # Integration tests (vectordotdev bindings)  
│   └── bindings.py           # Direct Python bindings tests
├── e2e/                      # End-to-end production tests
│   └── production_patterns.py # Real production pattern testing
└── fixtures/                 # Test data (no hardcoding)
    ├── test_patterns/        # Top 10 regex + grok patterns (2025 research)
    ├── test_data/            # Real production log samples
    └── test_configs/         # Test configuration mappings
```

**Test Types:**
- **Unit**: Isolated component testing using Vector subprocess (no mocks)
- **Integration**: Component interaction testing using vectordotdev Python bindings
- **E2E**: Full production scenarios with performance validation

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
/vectordotdev/          # Python code ONLY - CORE PURPOSE: Native in-app Vector execution
├── regex2vrl/         # Python regex→VRL conversion tool
├── tests/             # Python test suite (unit/integration/e2e)
├── examples/          # Python usage examples with THG benchmarking
├── src/vectordotdev/  # Main Python package for native Vector execution
│   ├── __init__.py    # Native Vector API with YAML/TOML config support
│   ├── thg_performance.py  # THG scoring and benchmarking system
│   └── vector_test_utils.py  # Vector runtime utilities
├── pyproject.toml     # Python package configuration
└── config.py          # Python configuration utilities

/vector-bindings/      # Rust code ONLY (PyO3 bindings)
├── src/
│   └── lib.rs         # PyO3 bindings entry point
├── vector_deps.toml   # Auto-detection configuration (no hardcoded versions)
├── build.rs           # Build-time Vector version detection
├── Cargo.toml         # Rust dependencies (auto-managed)
└── Cargo.lock         # Dependency lock (auto-generated)

/vector/               # Upstream Vector (Read-Only)
├── src/               # Vector Rust source code
├── target/            # Vector build artifacts  
└── Cargo.toml         # Vector dependencies

/build/                # Build System (Python orchestration)
├── build_system.py    # 3-stage build orchestrator
├── vector_detection.py # Version auto-detection with web fetch
├── core_build.py      # Stage execution engine
└── dependency_sync.py # Cross-component dependency sync
```

### Linting and Formatting Scope
- **Python linting**: Only applies to `/vectordotdev/` directory (pure Python)
- **Rust formatting**: Only for `/vector-bindings/` directory (PyO3 bindings)
- **Vector source**: Read-only, no formatting applied
- **Build system**: Python formatting for `/build/` directory

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

## Component Documentation

**IMPORTANT**: Keep these documentation files updated as the project evolves:

- **[README.md](README.md)** - Main project overview and quick start
- **[VECTOR.md](VECTOR.md)** - Vector core data processing engine (Stage 1)
- **[VECTOR-BINDINGS.md](VECTOR-BINDINGS.md)** - Rust bindings intermediate layer (Stage 2)  
- **[VECTORDOTDEV.md](VECTORDOTDEV.md)** - Python integration and regex2vrl (Stage 3)
- **[BUILD.md](BUILD.md)** - Build automation and orchestration system
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes

**Documentation Maintenance**: When making changes to any component, update the corresponding .md file to reflect current status, capabilities, and any limitations discovered.

## Common Development Tasks
1. **Adding new Vector features**: Vector features auto-detected via build system 
2. **Testing changes**: Use comprehensive test suite in `vectordotdev/tests/`
3. **Performance testing**: Use regex2vrl with Vector integration tests
4. **Manual dependency update**: Run `./scripts/update-deps.sh` for latest versions
5. **Build system**: Use `./build/build --verbose` for all compilation
6. **Documentation**: Update component .md files when making changes

## regex2vrl Status and Testing (v0.2.1)

### Current Status ✅
**regex2vrl is now production-ready** with real Vector CLI validation and comprehensive VRL generation capabilities.

**Version**: 0.2.2 (2025-09-08)
**Success Rate**: 86.7% on production patterns (13/15 patterns working)
**Performance**: 350+ THG target with built-in parsers
**Security**: HyperSec policy compliant (no regex functions in generated VRL)

### Key Achievements ✅
- **Real Vector Execution**: 100% log processing success rate with Vector CLI subprocess calls
- **No Mock Dependencies**: All tests use real `RegexToVRL()` and `GrokToVRL()` implementations
- **VRL Syntax Compliance**: Fixed all E103/E651 errors, uses proper `to_string()` and `merge!()`
- **YAML Configuration**: All Vector configs use YAML format with memory buffers
- **Production Patterns**: Successfully handles Apache, Nginx, Docker, Kubernetes, Syslog logs
- **Built-in Parsers**: JSON, key-value, timestamp extraction working at optimal performance
- **Complex Pattern Support**: Multi-field regex and grok pattern conversion working

### Technical Implementation ✅
**VRL Generation Engine** (`working_vrl_engine.py`):
- Type safety: `message_str = to_string(.message) ?? ""`
- Array access: `strip_whitespace(to_string(parts[i]))` (prevents E103 errors)
- Error handling: `parsed, err = parse_json()` + `if err == null` pattern
- Performance optimization: Built-in parsers (JSON, syslog, key-value) for 350+ THG

**Test Infrastructure** (`tests/unit/test_regex2vrl_subprocess.py`):
- Real Vector subprocess execution with `.tmp/` temp directories
- YAML configuration with memory buffers (`buffer: {type: memory}`)
- Comprehensive field validation and result verification
- No shell escaping issues (file-based configuration)

### Current Test Results ✅
```
Production Pattern Test Summary:
  Total Patterns: 15 (10 regex + 5 grok)
  Successful: 13 ✅ (86.7%)
  Failed: 2 ❌ (HAProxy HTTP, Postfix SMTP)  
  
Working Patterns:
  ✅ Apache Combined Logs (10 fields extracted)
  ✅ Nginx Access Logs (9 fields extracted)  
  ✅ Docker Container Logs (4/4 fields - 100%)
  ✅ Kubernetes Pod Logs (4/4 fields - 100%)
  ✅ JSON Application Logs (perfect parsing)
  ✅ Syslog Standard (multi-field parsing)
  ✅ ISO 8601 Timestamps (100% extraction)
  ✅ Log Level Detection (DEBUG/INFO/ERROR)
  ✅ HTTP Status Codes (1xx-5xx detection)
  ✅ MySQL Error Logs (database log parsing)
  ✅ AWS ELB Logs (complex load balancer logs)
```

### Known Limitations ⚠️
- **HAProxy HTTP Grok**: Complex multi-field pattern needs VRL optimization
- **Postfix SMTP Grok**: Mail server log parsing requires pattern refinement
- **Field Mapping**: Some patterns extract to intermediate fields vs exact expected names

### TODO: Comprehensive Testing Goal 🎯
**PRIORITY**: Achieve 100% success rate on ALL production regex and grok patterns with complete field extraction validation.

**Comprehensive Testing Scope**:
- **All Source Types**: Test with all log sources (file, syslog, json, csv, etc.)
- **All Regex Patterns**: Complete validation of production_regex_patterns.yaml (10 patterns)
- **All Grok Patterns**: Complete validation of production_grok_patterns.yaml (10 patterns)  
- **All Sample Data**: Test against production_log_samples.yaml (real-world logs)
- **Field Extraction**: 100% field extraction rate for all expected fields
- **Performance Validation**: Verify 350+ THG targets achieved across all patterns
- **Edge Case Handling**: Test malformed logs, empty logs, unicode, large logs
- **Integration Testing**: Validate with vectordotdev Python bindings
- **CEF/Auditd Support**: Comprehensive testing of security log formats

**Test Command**: `python tests/e2e/production_patterns.py --comprehensive --all-sources --field-validation`

**Success Criteria**:
- 100% pattern conversion success rate
- 95%+ field extraction accuracy
- 350+ THG performance on complex patterns
- Zero VRL compilation errors
- Real Vector CLI execution throughout

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