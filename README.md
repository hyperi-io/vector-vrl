# pyvector-rs

**High-performance Python bindings for Vector data processing pipelines**

[![License](https://img.shields.io/badge/License-HyperSec%20EULA-blue.svg)](https://hypersec.io/eula)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

pyvector-rs integrates the power of [Vector](https://vector.dev/) data processing pipelines directly into Python applications with minimal overhead. Built with Rust and PyO3 for maximum performance.

## 🚀 Features

- **High Performance**: Rust-powered Vector integration with minimal copying
- **Async/Await Support**: Native Python async/await interface
- **Multiple Sinks**: Send data to AWS S3, SQS, Elasticsearch, HTTP endpoints, files, and more
- **Zero-Copy Processing**: Efficient data handling between Python and Vector
- **Auto-Updating**: Automatically uses latest Vector releases
- **Cross-Platform**: Works on Linux, macOS, and Windows

## 📦 Installation

### From PyPI (when published)
```bash
pip install pyvector-rs
```

### From Source
```bash
# Clone the repository
git clone https://github.com/vectordotdev/pyvector-rs.git
cd pyvector-rs

# Install system dependencies (Linux/macOS)
./scripts/bootstrap.sh

# Build and install
uv run maturin develop
```

## 🏃 Quick Start

```python
import asyncio
import json
import pyvector

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
    vector = pyvector.Vector(config)
    
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

vector = pyvector.Vector(config)
await vector.start()

# Data automatically goes to S3, Elasticsearch, and SQS
await vector.send("python", json.dumps({"event": "user_login"}).encode())
```

### High-Throughput Processing

```python
import asyncio
import uuid

async def high_throughput_example():
    vector = pyvector.Vector(config)
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
pyvector-rs/
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
uv run pytest tests/ --cov=pyvector

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

### `pyvector.Vector`

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

## 📊 Performance

pyvector-rs is designed for high-throughput scenarios:

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
