# vectordotdev Build System

Dedicated build environment for the vectordotdev project.

## Usage

```bash
# From project root
./build/build --help        # Show help
./build/build --verbose     # Verbose build  
./build/build --clean       # Clean build
```

## Features

- **3-stage build process**: Vector core → Vector bindings → Python bindings
- **Heartbeat monitoring**: Detects stalls without timeouts
- **Version fallback**: Tries older Vector versions on upstream failures
- **Isolated environment**: Own Python venv and dependencies

## Directory Contents

- `build_system.py` - Main build logic
- `build` - Build launcher script
- `pyproject.toml` - Build system dependencies
- `.venv/` - Isolated Python environment