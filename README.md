# vectordotdev - Python Vector Data Processing Integration

[![Version](https://img.shields.io/badge/version-0.2.0-blue)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Build Status](https://img.shields.io/badge/build-3--stage-brightgreen)](#build-process)

Python bindings for Vector data processing pipelines with high-performance regex2vrl conversion tool and comprehensive testing infrastructure.

## 🚀 Features

- **High Performance**: Rust-powered Vector integration with minimal copying
- **Async/Await Support**: Native Python async/await interface
- **VRL Syntax Validation**: Fast VRL syntax checking with detailed error reporting
- **Multiple Sinks**: Send data to AWS S3, SQS, Elasticsearch, HTTP endpoints, files, and more
- **Zero-Copy Processing**: Efficient data handling between Python and Vector
- **Auto-Updating**: Automatically uses latest Vector releases
- **Cross-Platform**: Works on Linux, macOS, and Windows

## 📦 Installation

### From PyPI (when published)
```bash
pip install vectordotdev
```

### From Source
```bash
# Clone the repository
git clone https://github.com/vectordotdev/vectordotdev.git
cd vectordotdev

# Install system dependencies (Linux/macOS)
./scripts/bootstrap.sh

# Build and install
uv run maturin develop
```

## 🏃 Quick Start

```python
import asyncio
import json
import vectordotdev

# Configure Vector pipeline
config = """
[sources.python]
type = "python"

[sinks.file]
type = "file"
inputs = ["python"]
path = "/tmp/output.json"
encoding.codec = "json"
"""

async def main():
    # Create Vector instance
    vector = vectordotdev.Vector(config)
    
    # Start the pipeline
    await vector.start()
    
    # Send data
    for i in range(1000):
        data = json.dumps({
            "id": i,
            "message": f"Hello from Python {i}",
            "timestamp": "2024-01-01T12:00:00Z"
        }).encode()
        await vector.send("python", data)
    
    # Stop the pipeline
    await vector.stop()

# Run
asyncio.run(main())
```

### VRL Syntax Checking

```python
import vectordotdev

# Fast VRL syntax validation
result = vectordotdev.check_vrl_syntax('''
. = parse_json!(.message)
.timestamp = now()
.level = upcase(.level)
''')

if result.valid:
    print("✓ VRL syntax is valid")
else:
    print(f"✗ VRL error: {result.error}")
    if result.line:
        print(f"  Line {result.line}, Column {result.column}")

# Check multiple scripts
scripts = {
    "parser": '. = parse_json!(.message)',
    "enricher": '.timestamp = now()',
    "invalid": 'bad syntax'
}

results = vectordotdev.check_vrl_batch(scripts)
for name, result in results.items():
    status = "✓" if result.valid else "✗"
    print(f"{status} {name}: {result.message}")
```

## 🔧 Advanced Usage

### Multiple Destinations

Send the same data to multiple destinations simultaneously:

```python
config = """
[sources.python]
type = "python"

[sinks.s3]
type = "aws_s3"
inputs = ["python"]
bucket = "my-logs-bucket"
key_prefix = "app-logs/"
encoding.codec = "json"

[sinks.elasticsearch]
type = "elasticsearch"
inputs = ["python"]
endpoints = ["http://localhost:9200"]
index = "app-logs"
encoding.codec = "json"

[sinks.sqs]
type = "aws_sqs"
inputs = ["python"]
queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue"
encoding.codec = "json"
"""

vector = vectordotdev.Vector(config)
await vector.start()

# Data automatically goes to S3, Elasticsearch, and SQS
await vector.send("python", json.dumps({"event": "user_login"}).encode())
```

### High-Throughput Processing

```python
import asyncio
import uuid

async def high_throughput_example():
    vector = vectordotdev.Vector(config)
    await vector.start()
    
    # Send 1 million events efficiently
    tasks = []
    for i in range(1_000_000):
        data = json.dumps({
            "id": i,
            "uuid": str(uuid.uuid4()),
            "batch": i // 1000,
            "data": f"Event {i}"
        }).encode()
        tasks.append(vector.send("python", data))
        
        # Process in batches to avoid memory issues
        if len(tasks) >= 1000:
            await asyncio.gather(*tasks)
            tasks.clear()
    
    # Process remaining tasks
    if tasks:
        await asyncio.gather(*tasks)
    
    await vector.stop()
```

### Data Transformation

Use Vector's powerful transformation capabilities:

```python
transform_config = """
[sources.python]
type = "python"

[transforms.parse_and_enrich]
type = "remap"
inputs = ["python"]
source = '''
# Parse JSON and add metadata
. = parse_json!(.message)
.processed_at = now()
.hostname = get_hostname!()
.enriched = true
'''

[sinks.file]
type = "file"
inputs = ["parse_and_enrich"]
path = "/tmp/enriched.json"
encoding.codec = "json"
"""
```

## 🏗️ Project Structure

```
vectordotdev/
├── src/                    # Rust source code
│   ├── lib.rs             # Main Python module entry point
│   ├── vector_app.rs      # Vector application lifecycle management  
│   ├── python_source.rs   # Custom Python source for Vector
│   └── vector_context.rs  # Global Vector runtime context
├── tests/                  # Comprehensive Python test suite
│   ├── conftest.py        # Pytest configuration and fixtures
│   ├── test_basic.py      # Basic functionality tests
│   ├── test_vector_lifecycle.py  # Lifecycle management tests
│   ├── test_data_processing.py   # Data processing tests
│   ├── test_performance.py       # Performance and throughput tests
│   ├── test_package_integration.py  # PyPI package tests
│   ├── test_config_validation.py    # Configuration validation
│   └── test_edge_cases.py          # Edge cases and error handling
├── scripts/               # Build and maintenance scripts
│   ├── bootstrap.sh      # Multi-platform dependency installer
│   └── update-deps.sh    # Dependency update management
├── build.rs              # Dynamic version detection build script
├── Cargo.toml           # Rust dependencies (auto-updating)
├── pyproject.toml       # Python package configuration
├── LICENSE              # Apache 2.0 License
├── README.md           # This file
└── CLAUDE.md          # Development guide
```

### Source Code Architecture

**`src/lib.rs`** - Main Python Module
- Exports the `Vector` Python class
- Handles PyO3 bindings and module initialization
- Provides the main user interface: `Vector(config)`, `await vector.start()`, etc.

**`src/vector_app.rs`** - Vector Application Lifecycle
- Manages Vector application states: `Pending` → `Running` → `Stopped`
- Handles Vector topology creation and management
- Provides async start/stop operations
- Manages signal handling and graceful shutdown

**`src/python_source.rs`** - Custom Python Source Implementation
- Implements a custom "python" source type for Vector
- Provides channel-based communication between Python and Vector
- Handles JSON deserialization and data validation
- Manages data flow from Python into Vector pipelines

**`src/vector_context.rs`** - Global Runtime Context
- Manages shared Vector runtime and global state
- Initializes Vector metrics, logging, and SSL certificates
- Provides singleton pattern for Vector context
- Handles signal subscriptions for lifecycle management

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
uv run pytest tests/

# Run specific test categories  
uv run pytest tests/test_performance.py -v
uv run pytest tests/ -m "not slow" -v

# Run with coverage
uv run pytest tests/ --cov=vectordotdev

# Performance tests only
uv run pytest tests/ -m performance -v
```

Test categories:
- **Basic Tests**: Core functionality verification
- **Lifecycle Tests**: Start/stop/restart scenarios  
- **Data Processing**: JSON handling, transforms, multiple sinks
- **Performance Tests**: Throughput, concurrency, large data
- **Package Integration**: PyPI compatibility, imports, error handling
- **Config Validation**: Configuration parsing and validation
- **Edge Cases**: Error conditions, boundary cases, malformed data

## 🔧 Development

### Prerequisites

Install all required dependencies:

```bash
./scripts/bootstrap.sh
```

### Building

```bash
# Development build
uv run maturin develop

# With all compatibility flags for first build
RUSTFLAGS="-C linker=gcc" PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 uv run maturin develop

# Release build
uv run maturin build --release
```

### Dependency Management

The project uses **automatic dependency management**:

```bash
# Update all dependencies to latest compatible versions
./scripts/update-deps.sh

# Update to bleeding-edge versions (may include breaking changes)
./scripts/update-deps.sh --all
```

**Key Features:**
- 🔄 **Auto-updating Vector**: Always uses latest stable Vector release
- 📈 **Flexible versioning**: Uses `>=X.Y.Z` constraints for automatic updates  
- 🛡️ **Stability-first**: Prefers stable releases over pre-release versions
- 🔧 **Environment controls**: Skip updates with `SKIP_VECTOR_UPDATE=1`

## 🌟 API Reference

### `vectordotdev.Vector`

The main class for Vector pipeline management.

#### Constructor
```python
Vector(config: str) -> Vector
```
Create a new Vector instance with the specified TOML configuration.

#### Methods

**`async start()`**
Start the Vector pipeline. Must be called before sending data.

**`async stop()`**  
Stop the Vector pipeline and clean up resources.

**`async send(source: str, data: bytes)`**
Send data to a specific Vector source.
- `source`: Name of the source (as defined in config)
- `data`: Raw bytes to send (typically JSON-encoded)

### VRL Syntax Validation

Fast VRL syntax checking functions - no Vector instance required:

#### `check_vrl_syntax(vrl_code: str) -> VrlResult`

Check VRL syntax as fast as possible with full error details:

```python
import vectordotdev

# Valid VRL
result = vectordotdev.check_vrl_syntax('. = parse_json!(.message)')
print(result.valid)      # True
print(result.error_code) # 0

# Invalid VRL
result = vectordotdev.check_vrl_syntax('invalid syntax')
print(result.valid)      # False  
print(result.error_code) # 1
print(result.error)      # Error message
print(result.line)       # Line number (if available)
print(result.column)     # Column number (if available)
```

#### `check_vrl_batch(scripts: dict) -> dict`

Check multiple VRL scripts at once:

```python
scripts = {
    "parse": '. = parse_json!(.message)',
    "enrich": '.timestamp = now()',
    "invalid": 'bad syntax here'
}

results = vectordotdev.check_vrl_batch(scripts)
for name, result in results.items():
    print(f"{name}: {'✓' if result.valid else '✗'}")
```

#### `validate_vrl_transform(config: str) -> VrlResult`

Validate VRL in Vector transform configuration:

```python
transform_config = """
[transforms.parse]
type = "remap"
source = '''
. = parse_json!(.message)
.processed = true
'''
"""

result = vectordotdev.validate_vrl_transform(transform_config)
print(f"Transform valid: {result.valid}")
```

#### `get_vrl_functions() -> list[str]`

Get list of all available VRL functions:

```python
functions = vectordotdev.get_vrl_functions()
print(f"Available VRL functions: {len(functions)}")
print(functions[:10])  # First 10 functions
```

#### `explain_vrl_function(name: str) -> str | None`

Get documentation for a VRL function:

```python
doc = vectordotdev.explain_vrl_function("parse_json")
if doc:
    print(doc)  # Function description and examples
```

### `VrlResult` Class

Result object for VRL validation:

- `valid: bool` - Whether VRL syntax is valid
- `error_code: int` - Return code (0 = success, 1+ = error)  
- `error: str | None` - Error message if invalid
- `line: int | None` - Error line number (if available)
- `column: int | None` - Error column number (if available)
- `message: str` - Human-readable result message

### CLI-Compatible Vector Instances

Start Vector instances with CLI-like parameters and switches:

#### `VectorCli(config: str | None, options: VectorCliOptions)`

Create Vector instance with CLI-compatible options:

```python
import vectordotdev

# Create CLI options (same as Vector CLI switches)
opts = vectordotdev.VectorCliOptions(
    config_path="/path/to/vector.toml",    # --config
    verbose=2,                             # -vv  
    log_format="json",                     # --log-format json
    require_healthy=True,                  # --require-healthy
    dry_run=False,                         # --dry-run
    threads=4,                             # --threads 4
    config_vars={"ENV": "prod"}            # --config-var ENV=prod
)

# Create Vector with CLI options
vector = vectordotdev.VectorCli(config_string, opts)
await vector.start()
```

#### `vector_from_cli_args(args: list, config: str = None)`

Create Vector from CLI-style arguments:

```python
# Exactly like Vector CLI
args = [
    "--config", "/etc/vector/vector.toml",
    "--verbose", "--verbose",              # -vv
    "--log-format", "json", 
    "--require-healthy",
    "--threads", "8",
    "--config-var", "DATA_DIR=/var/lib/vector",
    "--config-var", "LOG_LEVEL=debug"
]

vector = vectordotdev.vector_from_cli_args(args)
await vector.start()
```

#### `VectorCliOptions` Parameters

All Vector CLI switches supported:

- `config_path: str` - Config file path (`--config`)
- `config_dir: str` - Config directory (`--config-dir`)  
- `watch_config: bool` - Watch config changes (`--watch-config`)
- `verbose: int` - Verbosity level (`-v`, `-vv`, `-vvv`)
- `quiet: bool` - Quiet mode (`--quiet`)
- `log_format: str` - Log format (`--log-format text|json`)
- `require_healthy: bool` - Require healthy start (`--require-healthy`)
- `dry_run: bool` - Dry run mode (`--dry-run`)
- `threads: int` - Thread count (`--threads N`)
- `internal_log_rate_limit: int` - Log rate limit (`--internal-log-rate-limit`)
- `allow_empty_config: bool` - Allow empty config (`--allow-empty-config`)
- `config_vars: dict` - Config variables (`--config-var KEY=VALUE`)

#### Config Validation Functions

```python
# Fast config syntax checking
valid = vectordotdev.check_config_syntax(config_string)
print(f"Config valid: {valid}")

# Validate config file
valid = vectordotdev.validate_config_file("/path/to/vector.toml")
print(f"File valid: {valid}")
```

## 📊 Performance

vectordotdev is designed for high-throughput scenarios:

- **1M+ messages/second**: Efficient async processing
- **Low latency**: Minimal overhead between Python and Vector
- **Memory efficient**: Zero-copy data handling where possible
- **Concurrent safe**: Multiple coroutines can send simultaneously

## 🤝 Contributing

1. Fork the repository
2. Install dependencies: `./scripts/bootstrap.sh`  
3. Make your changes
4. Run tests: `uv run pytest tests/`
5. Submit a pull request

## 📄 License

Copyright (c) 2025 HyperSec. This software is licensed under the HyperSec End User License Agreement (EULA). 

For complete license terms, visit: https://hypersec.io/eula

## 🔗 Related Projects

- [Vector](https://vector.dev/) - The core data processing engine
- [PyO3](https://pyo3.rs/) - Python bindings for Rust
- [maturin](https://github.com/PyO3/maturin) - Build tool for Python extensions
