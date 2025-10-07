# Vector Bindings

Python bindings for Vector using PyO3 with automatic API discovery.

## Overview

This directory contains Rust code that exposes Vector functionality to Python. APIs are automatically discovered from Vector source code at build time, requiring no manual maintenance.

**Current Status**: 83 APIs exposed (6 manual + 77 auto-discovered)

## Building

```bash
# Activate virtual environment
source .venv/bin/activate

# Build and install (development)
maturin develop --release

# Build wheel for distribution
maturin build --release
```

## Architecture

### Manual APIs (6)

Hand-written PyO3 bindings for complex functionality:
- `execute_vrl` - VRL execution engine
- `validate_vrl` - VRL syntax validation
- `get_vrl_performance` - Performance metrics
- `Vector`, `VrlResult`, `VrlTarget` - Supporting types

Located in: [src/lib.rs](src/lib.rs)

### Auto-Discovered APIs (77)

Automatically discovered from Vector source via `build.rs`:
- Event types (Event, LogEvent, Metric, TraceEvent, etc.)
- Metadata types (EventMetadata, EventStatus, etc.)
- Infrastructure types (BatchNotifier, ShutdownSignal, etc.)

Located in: Auto-generated in `OUT_DIR/auto_bindings.rs`

## Auto-Discovery System

### How It Works

1. **Build time** (`build.rs`): Scans Vector source directories
2. **AST parsing**: Uses `syn` crate to find public types
3. **Code generation**: Creates PyO3 wrapper types
4. **Integration**: Includes generated code via `include!()` macro

### Currently Scanned Modules

```rust
// In build.rs
let search_paths = vec![
    PathBuf::from("../vector/lib/vector-core/src/event"),
    PathBuf::from("../vector/lib/vector-common/src"),
];
```

### Adding More Modules

Edit `build.rs` and add paths to `search_paths`:

```rust
PathBuf::from("../vector/lib/vector-core/src/transform"),
PathBuf::from("../vector/lib/vector-core/src/source"),
PathBuf::from("../vector/lib/vector-core/src/sink"),
```

Then rebuild.

## When Vector Updates

When Vector adds new public types:

1. **Build**: `maturin develop --release`
   - `build.rs` discovers new types
   - PyO3 bindings generated automatically

2. **Document**: `python ../generate_api_docs.py`
   - Updates `API_REFERENCE.md` with new types

3. **Done**: No manual code changes needed

## Files

- `src/lib.rs` - Main bindings module with manual APIs
- `build.rs` - Auto-discovery system
- `Cargo.toml` - Dependencies and build configuration
- `API_REFERENCE.md` - Complete API documentation (auto-generated)

## Dependencies

### Runtime
- `pyo3` 0.22 - Python FFI
- `vrl` (main branch) - Vector Remap Language
- `ordered-float` - NotNan<f64> support

### Build
- `syn` 2.0 - Rust AST parser
- `quote` 1.0 - Code generation
- `walkdir` 2.5 - Directory traversal

## Testing

Run tests from project root:

```bash
# VRL execution tests
python test_auto_exposed_apis.py

# Unit tests
python -m pytest vectordotdev/tests/
```

## Documentation

- [API_REFERENCE.md](API_REFERENCE.md) - Complete API listing (auto-generated)
- [../IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md) - Implementation details
- [../AUTO_EXPOSURE_SUCCESS.md](../AUTO_EXPOSURE_SUCCESS.md) - Auto-discovery system details

## Troubleshooting

### Build fails with "type not found"

Check that Vector submodule is initialized:
```bash
cd ../vector
git submodule update --init
```

### Missing APIs

Verify the type is:
1. In a scanned module (`event` or `common`)
2. Public (`pub struct` or `pub enum`)
3. Not in the skip list (see `build.rs`)

Add more modules to `build.rs` to expand coverage.

### Documentation out of sync

Regenerate documentation:
```bash
python ../generate_api_docs.py
```

## Development Workflow

1. Make changes to `src/lib.rs` or `build.rs`
2. Build: `maturin develop --release`
3. Test: `python test_auto_exposed_apis.py`
4. Document: `python ../generate_api_docs.py`
5. Commit changes

## License

Same as parent project.
