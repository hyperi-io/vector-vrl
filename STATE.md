# vectordotdev Project State

**Last Updated**: October 7, 2025
**Version**: 1.0.5
**Status**: Production Ready

## Quick Start

1. **Read First**: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Complete architecture
2. **Current Tasks**: [TODO.md](TODO.md) - Active work items
3. **API Reference**: [vector-bindings/API_REFERENCE.md](vector-bindings/API_REFERENCE.md) - All exposed APIs

## Project Overview

Python package providing native Vector execution via Rust PyO3 bindings.

**Core Capabilities**:
- Native VRL execution (585k+ events/second, in-memory)
- Auto-exposure of Vector APIs (83 total: 6 manual + 77 auto-discovered)
- regex2vrl standalone converter (production-ready)
- THG benchmarking framework

## Current Status (v1.0.5)

### ✅ VRL In-Memory Execution - PRODUCTION READY
- Real VRL compiler and runtime via PyO3 bindings
- 585,898 events/second throughput
- No subprocess overhead
- All tests passing (5/5)

**Test File**: `vectordotdev/tests/unit/test_native_vrl_simple.py`

**Performance**:
```
Events/second: 585,898
Processing time: 3.4ms (2000 events)
Mode: In-process, no subprocess calls
```

### ✅ Auto-Exposure System - PRODUCTION READY
- 78 Vector APIs auto-discovered from source
- Zero maintenance required
- All tests passing (4/4)

**Build System**: `vector-bindings/build.rs`

**Coverage**:
- vector-core/src/event: 45 APIs
- vector-common/src: 33 APIs
- Total: 78 auto + 6 manual = 83 APIs

### ✅ regex2vrl - PRODUCTION READY
- Standalone VRL generator (no Vector runtime deps)
- 100% unit test pass rate
- Production patterns: Apache, Nginx, Docker, K8s, JSON, Syslog, AWS ELB, MySQL
- THG benchmarking: 350+ performance targets

## Architecture

### 4-Component Flow
```
/vector           → Vector source (1,291+ Rust files)
/vector-bindings  → PyO3 Rust bindings (auto-discovers Vector APIs)
/vectordotdev     → Python package (uses bindings)
/build            → Build automation system
```

### Build Process
```
1. build.rs scans /vector source
2. Discovers public types (struct/enum)
3. Generates PyO3 bindings automatically
4. Compiles to .so library
5. Python imports via vector_bindings module
```

## Key Features

### 1. Native VRL Execution

Execute VRL code directly in Python with full Vector runtime:

```python
from vectordotdev._bindings import execute_vrl

vrl_code = ".level = upcase!(.level)"
events = ['{"level": "info", "message": "test"}']
results = execute_vrl(vrl_code, events)
# [{"level": "INFO", "message": "test"}]
```

**APIs Available**:
- `execute_vrl(code, events)` - Execute VRL against events
- `validate_vrl(code)` - Validate VRL syntax
- `get_vrl_performance(code, events, iterations)` - Measure performance

### 2. Auto-Exposed Vector Types

83 Vector types automatically available in Python:

```python
from vectordotdev._bindings import (
    EventArray, EventStatus, LogEvent, Metric,
    BatchNotifier, ComponentKey, ShutdownSignal,
    # ... 76 more auto-discovered types
)
```

**How It Works**:
- `build.rs` scans Vector source at build time
- Uses `syn` crate for AST parsing
- Generates PyO3 wrappers automatically
- No manual maintenance required

### 3. regex2vrl Converter

Standalone VRL generator for log parsing:

```python
from vectordotdev.regex2vrl import RegexToVRL

converter = RegexToVRL()
vrl_code = converter.convert(
    pattern=r'^(?P<ip>\S+) - (?P<user>\S+) \[(?P<timestamp>[^\]]+)\]',
    example='192.168.1.1 - admin [01/Jan/2025:00:00:00 +0000]'
)
```

### 4. THG Benchmarking

Performance measurement framework:

```python
from vectordotdev.benchmarks import THGBenchmark

benchmark = THGBenchmark()
score = benchmark.run(vrl_code, test_data)
```

## Work Directories

### Vector (Rarely Needed)
```bash
cd vector
cargo build --release
```

### Rust Bindings (For API Changes)
```bash
cd vector-bindings
.venv/bin/maturin develop --release

# Regenerate API docs after build
cd ..
python generate_api_docs.py
```

### Python Package (Most Common)
```bash
cd vectordotdev
PYTHONPATH=src python tests/unit/test_native_vrl_simple.py
PYTHONPATH=src python -c "from vectordotdev.regex2vrl import RegexToVRL"
```

### Build System
```bash
cd build
python build_system.py --verbose
```

## Critical Rules

1. **Component Isolation**: Always `cd` to component directory before work
2. **Python Paths**: Use `PYTHONPATH=src` for vectordotdev testing
3. **No Hardcoding**: Dependencies from source, not version strings
4. **VRL Operators**: Use `!` for fallible operations (e.g., `upcase!()`)
5. **Build Order**: vector → vector-bindings → vectordotdev

## Common Commands

### Testing
```bash
# VRL in-memory tests
python vectordotdev/tests/unit/test_native_vrl_simple.py

# Auto-exposure tests
python test_auto_exposed_apis.py

# regex2vrl tests
cd vectordotdev && PYTHONPATH=src python tests/run_tests.py --category unit
```

### Building
```bash
# Build bindings
cd vector-bindings && .venv/bin/maturin develop --release

# Generate API docs
python generate_api_docs.py
```

### Development
```bash
# Add new Vector modules to auto-discovery
# Edit: vector-bindings/build.rs
# Add path to search_paths vector
# Rebuild and regenerate docs
```

## Test Status

| Test Suite | Tests | Status | Performance |
|------------|-------|--------|-------------|
| VRL In-Memory | 5 | ✅ 5/5 PASSING | 585,898 EPS |
| Auto-Exposure | 4 | ✅ 4/4 PASSING | 78 APIs |
| regex2vrl | 100+ | ✅ PASSING | Production Ready |

## Documentation

### Core Documentation
- [README.md](README.md) - Project overview and getting started
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Complete architecture
- [CHANGELOG.md](CHANGELOG.md) - Version history

### Component Documentation
- [vector-bindings/README.md](vector-bindings/README.md) - Rust bindings developer guide
- [vector-bindings/API_REFERENCE.md](vector-bindings/API_REFERENCE.md) - Complete API listing (auto-generated)
- [BUILD.md](BUILD.md) - Build system documentation

### Implementation Guides
- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) - Current implementation status
- [TODO.md](TODO.md) - Active tasks and roadmap

## Key Files

### Auto-Discovery System
- `vector-bindings/build.rs` - Auto-discovers Vector APIs from source
- `vector-bindings/src/lib.rs` - Main bindings with manual APIs
- `generate_api_docs.py` - Auto-generates API documentation

### Tests
- `vectordotdev/tests/unit/test_native_vrl_simple.py` - VRL execution tests
- `test_auto_exposed_apis.py` - Auto-exposure verification
- `vectordotdev/tests/unit/test_vrl_in_memory.py` - Comprehensive VRL tests

### Core Implementation
- `vectordotdev/src/vectordotdev/regex2vrl/` - regex2vrl converter
- `vectordotdev/src/vectordotdev/benchmarks/` - THG benchmarking
- `build/` - Build automation system

## Environment

### Temp Files
- Use `./.tmp/` only (never `/tmp`, `~/`)
- Auto-created by build system

### Configuration
- dynaconf for config management
- `VECTORDOTDEV_` environment prefix
- `settings.toml` for local settings

### Dependencies
- Python 3.13+
- Rust 1.70+
- Vector (from git submodule or auto-detected)
- PyO3 0.22+

## Version History

### v1.0.5 (October 7, 2025) - Current
- ✅ VRL in-memory execution (585k+ EPS)
- ✅ Auto-exposure system (78 APIs)
- ✅ Auto-generated API documentation
- ✅ Comprehensive test suite (9/9 passing)

### v1.0.4 (October 7, 2025)
- Fixed VRL API compatibility (v0.27)
- Removed hardcoded VRL version
- Updated to VRL from git main

### v1.0.3 (September 22, 2025)
- regex2vrl production release
- THG benchmarking framework
- Build system automation

## Troubleshooting

### Build Issues

**Problem**: `maturin develop` fails
```bash
cd vector-bindings
rm -rf target
.venv/bin/maturin develop --release
```

**Problem**: APIs missing after Vector update
```bash
cd vector-bindings
.venv/bin/maturin develop --release
cd ..
python generate_api_docs.py
```

### Import Errors

**Problem**: `No module named 'vector_bindings'`
```bash
cd vector-bindings
.venv/bin/maturin develop --release
```

**Problem**: `No module named 'vectordotdev'`
```bash
cd vectordotdev
PYTHONPATH=src python your_script.py
```

### VRL Errors

**Problem**: "unhandled fallible assignment"
- Use `!` operator for fallible functions
- Example: `.level = upcase!(.level)` not `.level = upcase(.level)`

**Problem**: "call to undefined function"
- Check VRL function exists in stdlib
- Verify function name spelling

## Future Roadmap

### Potential Expansions (Easy)
1. More Vector modules (transform, source, sink) - 30 minutes
2. More VRL test files - 1 hour
3. Integration tests for auto-exposed types - 2 hours

### Potential Enhancements
1. Better VRL error handling
2. VRL debugging/tracing support
3. Async VRL execution
4. Direct Vector pipeline creation from Python

## Getting Help

- **Issues**: Check TODO.md for known issues
- **API Reference**: See vector-bindings/API_REFERENCE.md
- **Examples**: Check vectordotdev/tests/ directory
- **Build Problems**: See BUILD.md troubleshooting section

---

**Project Status**: ✅ Production Ready
**Last Test Run**: October 7, 2025
**All Tests**: 9/9 PASSING
**Performance**: 585,898 EPS (VRL in-memory)
