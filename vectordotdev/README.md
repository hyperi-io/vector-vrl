# vectordotdev - Native In-App Vector Execution for Python

**Execute Vector data processing pipelines directly in Python applications without subprocess calls.**

## Core Purpose

vectordotdev enables **native in-app Vector execution** via PyO3 bindings, providing:

- 🚀 **In-process Vector execution** (no subprocess overhead)
- 📝 **YAML/TOML config support** (supply configs as Python dicts)  
- 🎯 **Native error handling** (Python exceptions, no text parsing)
- 📊 **THG performance benchmarking** (consistent scoring and optimization)
- 📦 **Single PyPI package** (complete Vector runtime embedded)

## Installation

```bash
pip install vectordotdev
```

## Quick Start: Native Vector Execution

```python
import vectordotdev

# Configure Vector pipeline (YAML/TOML as Python dict)
config = {
    "sources": {
        "logs": {"type": "stdin"}
    },
    "transforms": {
        "parse": {
            "type": "remap",
            "source": """
                parsed, err = parse_json(.message)
                if err == null {
                    .level = parsed.level
                    .timestamp = parsed.timestamp
                }
            """
        }
    },
    "sinks": {
        "output": {"type": "console", "encoding": {"codec": "json"}}
    }
}

# Execute Vector pipeline in-process (no subprocess)
vector = vectordotdev.Vector(config)
vector.initialize()

# Process logs natively in Python process
input_logs = [
    '{"level": "INFO", "timestamp": "2023-09-08T12:00:00Z", "message": "User login"}',
    '{"level": "ERROR", "timestamp": "2023-09-08T12:00:01Z", "message": "Auth failed"}'
]

results = vector.process_logs(input_logs)  # Native in-memory processing
stats = vector.get_stats()                 # Native metrics collection

print(f"Processed {len(results)} events")
print(f"Performance: {stats}")
```

## THG Performance Assessment

```python
# Assess VRL performance with THG scoring
vrl_code = '''
    parsed, err = parse_json(.message)
    if err == null {
        .level = parsed.level
        .service = parsed.service
    }
'''

test_logs = ['{"level": "INFO", "service": "api"}', '{"level": "ERROR", "service": "auth"}']

# Get comprehensive performance assessment
thg_result = vectordotdev.assess_vrl_performance(vrl_code, test_logs, "json_parser")

print(f"THG Score: {thg_result['thg_score']}")           # 0-1000+ performance rating
print(f"Grade: {thg_result['performance_grade']}")       # A+ through F
print(f"Throughput: {thg_result['events_per_second']} eps")
print(f"Recommendations: {thg_result['recommendations']}")  # Optimization tips
```

## Native Error Handling

```python
try:
    vector = vectordotdev.Vector(invalid_config)
    vector.initialize()
    results = vector.process_logs(data)
except vectordotdev.VectorConfigError as e:
    print(f"Configuration error: {e.details}")  # Structured error object
except vectordotdev.VRLSyntaxError as e:  
    print(f"VRL syntax error: {e.line}, {e.column}")  # Precise error location
except vectordotdev.VectorRuntimeError as e:
    print(f"Runtime error: {e.component}, {e.message}")  # Component-specific error
```

## Features

- **🚀 Native execution**: 10x+ faster than subprocess Vector
- **📝 Config flexibility**: YAML, TOML, or Python dict configurations
- **🎯 Error precision**: Structured error objects with precise locations  
- **📊 THG benchmarking**: Performance scoring and optimization guidance
- **🔧 Production ready**: Complete Vector feature set in Python

## Performance Benefits

| Execution Method | Performance | Memory | Error Handling | Integration |
|------------------|-------------|--------|----------------|-------------|
| **vectordotdev (in-process)** | **10x+ faster** | **Shared memory** | **Python exceptions** | **Native** |
| Command-line Vector | Baseline | Separate process | Text parsing required | Subprocess |

## Documentation

See the main project documentation for complete API reference, build instructions, and Vector integration examples.