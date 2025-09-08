# VECTORDOTDEV.md - Python Integration & regex2vrl

**Stage 3 of the 4-component architecture**

## 🎯 **Purpose**

The `/vectordotdev` directory contains the **Python integration layer** with PyO3 bindings, the regex2vrl conversion tool, and comprehensive testing infrastructure.

## 🏗️ **Role in Build Pipeline**

```
/vector (Stage 1) → /vector-bindings (Stage 2) → /vectordotdev (Stage 3)
                                                        ↑
                              /build (Orchestrator) ────┘
```

**Position**: **Application layer** - Python API and user-facing functionality  
**Dependencies**: vector-bindings (Stage 2), Vector (Stage 1)  
**Dependents**: End-user Python applications  
**Build**: Final stage of 3-stage build system

## 📁 **Directory Structure**

```
/vectordotdev/                  # PURE PYTHON ONLY
├── regex2vrl/                  # High-performance regex → VRL converter
│   ├── core.py                # Main conversion engine  
│   ├── grok_converter.py      # Grok pattern support
│   ├── cli.py                 # Command-line interface
│   └── README.md              # regex2vrl documentation
├── tests/                      # Comprehensive test suite (NO MOCKS)
│   ├── unit/                  # Vector subprocess tests (100% success)
│   ├── integration/           # Python bindings tests  
│   ├── e2e/                   # Production scenario tests
│   ├── fixtures/              # Test patterns and data (no hardcoding)
│   └── run_tests.py           # Main test runner
├── examples/                   # Usage examples
│   └── example.py             # Basic Vector integration example
├── version_detection.py       # Vector version auto-detection (Python)
├── config.py                  # Configuration utilities (Python)
├── __init__.py                # Python package initialization
├── pyproject.toml             # Python package configuration (NO Cargo.toml)
└── README.md                  # Component documentation
```

**Architecture Principle**: `/vectordotdev` contains **ONLY Python code** and imports compiled bindings from `/vector-bindings`. No Rust source code should exist in this directory.

## ⚡ **Key Components**

### **🔄 regex2vrl - Pattern Conversion Tool**

**Purpose**: Convert regex and grok patterns to high-performance VRL code

**Performance Target**: **350+ THG rating** by using Vector built-ins instead of regex

#### **Features**
- **Regex → VRL**: Convert any regex pattern to performant VRL
- **Grok → VRL**: Full grok pattern support with automatic optimization  
- **Built-in Detection**: Automatically uses Vector's optimized parsers
- **Pattern Analysis**: Performance analysis before deployment
- **Batch Conversion**: Convert multiple patterns at once

#### **Usage**
```python
from vectordotdev.regex2vrl import RegexToVRL, GrokToVRL

# Convert regex to VRL
converter = RegexToVRL()
regex = r'(?P<ip>\d+\.\d+\.\d+\.\d+) - (?P<user>\S+) \[(?P<timestamp>[^\]]+)\]'
vrl_code = converter.convert(regex)

# Convert grok to VRL  
grok_converter = GrokToVRL()
grok = '%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{GREEDYDATA:message}'
vrl_code = grok_converter.convert(grok)

# Analyze performance
analysis = converter.analyze_pattern(regex)
print(f"Estimated THG: {analysis.estimated_thg}")
```

#### **Production Patterns Supported**
Based on 2025 production research:
- **Apache Combined Log**: Most common web server format
- **Nginx Access Logs**: With X-Forwarded-For support
- **Syslog Standard**: RFC3164 system logs  
- **JSON Application**: Structured app logs
- **Docker/Kubernetes**: Container log formats
- **AWS ELB, HAProxy**: Load balancer logs

### **🧪 Testing Infrastructure**

**Zero-Mock Testing Philosophy**: All tests use real Vector execution

#### **Test Categories**
```
tests/
├── unit/                   # Isolated component tests (Vector subprocess)
│   ├── test_regex2vrl_subprocess.py  # 100% success rate
│   └── test_vrl_*.py      # VRL function tests
├── integration/            # Component interaction tests (Python bindings)
│   └── bindings.py        # vectordotdev bindings integration  
├── e2e/                   # End-to-end production tests
│   └── production_patterns.py  # Real pattern validation
└── fixtures/              # Test data (no hardcoding)
    ├── test_patterns/     # Top 10 regex + grok patterns  
    ├── test_data/         # Real production log samples
    └── test_configs/      # Configuration mappings
```

#### **Test Execution**
```bash
# All test categories
python tests/run_tests.py

# Individual categories
python tests/run_tests.py --category unit        # Vector subprocess (100% success)  
python tests/run_tests.py --category integration # Python bindings
python tests/run_tests.py --category e2e         # Production scenarios

# Direct test execution
python tests/unit/test_regex2vrl_subprocess.py --verbose
```

#### **Test Results Validation**
- **Unit Tests**: ✅ 100% success rate with real Vector subprocess
- **Integration Tests**: 🚧 Basic functionality working, transforms in development
- **Performance Tests**: ✅ THG validation and optimization confirmed

## 🔌 **Python API Interface**

### **Vector Class** (Primary Interface)
```python
import vectordotdev

# Create Vector instance
config = """
[sources.python]
type = "python"

[sinks.file]  
type = "file"
inputs = ["python"]
path = "/tmp/output.json"
encoding.codec = "json"
"""

vector = vectordotdev.Vector(config)
vector.start()  # Synchronous
vector.send("python", json.dumps(data).encode())
vector.stop()
```

### **VRL Utilities**
```python
import vectordotdev

# VRL syntax checking
is_valid = vectordotdev.vrl_check(".processed = true")

# Available VRL functions
functions = vectordotdev.vrl_functions()  
```

## 📊 **Current Status**

### ✅ **Working Features**  
- **Python Bindings**: Basic Vector class available
- **VRL Checking**: Syntax validation working  
- **regex2vrl**: Conversion tool with 100% subprocess validation
- **Config Parsing**: TOML configuration support
- **Data Flow**: Basic source→sink data flow confirmed

### 🚧 **In Development**
- **Transform Pipeline**: VRL transforms need full implementation
- **YAML Config**: Preferred format support (TOML deprecated with vector.dev)
- **Advanced Sinks**: Multiple sink type support
- **Async Interface**: Full async/await support matching Vector patterns

### 🎯 **Development Roadmap**

#### **Phase 1** (Current - v0.2.0)
- ✅ regex2vrl with 100% Vector validation  
- ✅ Comprehensive testing infrastructure
- ✅ Build system integration
- 🚧 Basic Python bindings foundation

#### **Phase 2** (Next - v0.3.0)
- 🎯 Full VRL transform execution
- 🎯 YAML configuration support  
- 🎯 Complete vectordotdev bindings implementation
- 🎯 Performance optimization

#### **Phase 3** (Future - v0.4.0+)
- 🎯 Advanced Vector features
- 🎯 Custom component development
- 🎯 Streaming and backpressure
- 🎯 Monitoring integration

## 🧪 **Testing Strategy**

### **Multi-Tier Validation**
1. **Unit Tests**: Validate individual components with Vector subprocess
2. **Integration Tests**: Test component interactions with Python bindings  
3. **E2E Tests**: Full production scenarios with performance validation

### **No-Mock Philosophy**
- **Real Vector**: All tests use actual Vector execution
- **Production Patterns**: Based on real-world log parsing requirements
- **Performance Validation**: THG metrics confirmed with actual Vector
- **Field Extraction**: Complete validation of parsed log fields

### **Test Configuration**  
All patterns and test data externalized to YAML files:
```yaml
# No hardcoded values in test code
apache_combined_log:
  pattern: '^(?P<ip>\d+\.\d+\.\d+\.\d+)...'
  expected_fields: [ip, method, status]
  sample_logs:
    - '192.168.1.100 - - [15/Jan/2025:10:30:45 +0000] "GET /index.html HTTP/1.1" 200 1024...'
```

## 🔧 **Development Guidelines**

### **Adding New Features**
1. **Follow Build System**: Use 3-stage build for all changes
2. **Add Tests First**: Create tests with real Vector validation
3. **Update Documentation**: Keep component docs current  
4. **No Hardcoding**: Use configuration or auto-detection

### **regex2vrl Development**
1. **Performance First**: Target 350+ THG for all patterns
2. **Built-in Detection**: Use Vector's optimized parsers when possible
3. **Test with Vector**: Validate all generated VRL with real Vector execution
4. **Production Focus**: Base patterns on real-world usage research

### **Python API Development** 
1. **Vector Compatibility**: Match Vector's async patterns
2. **Error Handling**: Provide detailed Python exceptions from Rust errors
3. **Memory Management**: Optimize data flow and minimize copying
4. **Documentation**: Keep API docs synchronized with implementation

## 🚨 **Known Issues & Workarounds**

### **Current Limitations**
- **Transform Pipeline**: VRL transforms not fully implemented in bindings
- **Async Interface**: Some methods synchronous instead of async
- **YAML Support**: Currently requires TOML format for bindings

### **Workarounds**
- **Use Subprocess Tests**: For comprehensive Vector validation
- **TOML Configuration**: Use TOML format until YAML support implemented  
- **Basic Operations**: Direct source→sink works for simple cases

## 📈 **Performance Metrics**

### **regex2vrl Performance** 
- **350+ THG**: Achieved for built-in parser patterns
- **300+ THG**: Achieved for optimized custom patterns
- **100% Accuracy**: All test patterns process correctly with Vector

### **Test Performance**
- **100% Unit Test Success**: All subprocess Vector tests passing
- **Real Vector Integration**: No mock dependencies
- **Production Validation**: Patterns based on real-world usage

---

**vectordotdev provides the Python interface** that makes Vector's powerful data processing capabilities accessible to Python applications with high performance and comprehensive testing validation.