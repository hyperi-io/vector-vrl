# vectordotdev

Python package for Vector data processing pipelines with regex2vrl conversion capabilities.

## Installation

```bash
pip install vectordotdev
```

## Quick Start

```python
from vectordotdev.regex2vrl import RegexToVRL

# Convert regex patterns to VRL for Vector
converter = RegexToVRL()
vrl_code = converter.convert_pattern(r'(\d+)\s+(\w+)', ['number', 'word'])
print(vrl_code)
```

## Features

- **regex2vrl conversion**: Convert regex patterns to Vector Remap Language
- **Production patterns**: Supports Apache, Nginx, Docker, Kubernetes logs
- **Performance optimized**: 350+ THG with built-in parsers
- **Vector integration**: Direct Vector CLI validation

## Documentation

See the main project documentation in the repository root for complete usage examples and API reference.