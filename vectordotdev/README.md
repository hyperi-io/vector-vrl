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

## Production Patterns

vectordotdev includes **pre-provisioned production patterns** for common log formats, optimized for native execution:

```python
# Apache Combined Logs (350+ THG)
apache_config = vectordotdev.get_apache_combined()
vector = vectordotdev.Vector(apache_config)
vector.initialize()

apache_logs = ['192.168.1.1 - user [08/Sep/2023:12:00:00 +0000] "GET /api HTTP/1.1" 200 1234']
results = vector.process_logs(apache_logs)  # Native 10-field extraction

# JSON Application Logs (500+ THG with built-in parsers)  
json_config = vectordotdev.get_json_application()
json_logs = ['{"level": "INFO", "service": "api", "request_id": "123"}']

# Kubernetes Pod Logs (300+ THG with metadata extraction)
k8s_config = vectordotdev.get_kubernetes_pods() 
k8s_logs = ["2023-09-08T12:00:00Z INFO [api-gateway] Server started"]

# Docker Container Logs (400+ THG with container parsing)
docker_config = vectordotdev.get_docker_container()
docker_logs = ["2023-09-08T12:00:00Z container_123[app]: Application ready"]

# Available patterns
patterns = vectordotdev.ProductionPatterns.list_available_patterns()
print(f"Available patterns: {patterns}")
```

### Supported Production Patterns

| Pattern | THG Target | Fields Extracted | Use Case |
|---------|------------|------------------|----------|
| **Apache Combined** | 350+ EPS | 10 fields | Web server access logs |
| **JSON Application** | 500+ EPS | 8+ fields | Structured app logs |  
| **Nginx Access** | 400+ EPS | 9 fields | Nginx web server logs |
| **Kubernetes Pods** | 300+ EPS | 6 fields | K8s orchestration logs |
| **Docker Container** | 400+ EPS | 4 fields | Container runtime logs |
| **Syslog Standard** | 250+ EPS | 7 fields | System/infrastructure logs |

All patterns are optimized for **native in-process execution** with comprehensive THG performance assessment.
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