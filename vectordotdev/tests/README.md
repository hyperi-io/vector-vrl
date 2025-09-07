# vectordotdev Test Suite

This directory contains comprehensive tests for the vectordotdev library, organized by test type following best practices.

## Overview

The test suite validates vectordotdev functionality including:
1. **Unit Tests**: Isolated component testing (VRL functions, subprocess Vector calls)
2. **Integration Tests**: Component interaction testing (vectordotdev Python bindings)
3. **E2E Tests**: End-to-end production scenarios (regex2vrl with real patterns)

## Test Structure

```
vectordotdev/tests/
├── run_tests.py                       # Main test runner
├── unit/                              # Unit tests (isolated components)
│   ├── subprocess.py                  # Vector subprocess unit tests
│   └── test_vrl_*.py                  # VRL function unit tests
├── integration/                       # Integration tests (component interaction)
│   └── bindings.py                    # vectordotdev bindings integration tests
├── e2e/                               # End-to-end tests (full scenarios)
│   ├── production_patterns.py         # Production pattern E2E tests
│   ├── regex2vrl.py                   # Full regex2vrl pipeline tests
│   └── run_regex2vrl_tests.py         # Legacy comprehensive test runner
└── fixtures/                          # Shared test data and configurations
    ├── test_patterns/                 # Production regex/grok patterns
    ├── test_data/                     # Real log samples
    └── test_configs/                  # Test configuration mappings
```

## Test Categories

### Unit Tests (`unit/`)
**Isolated component testing - NO dependencies between tests**

- **VRL Function Tests**: Test individual VRL functions (parse_json, split, etc.)
- **Subprocess Tests**: Test regex2vrl → VRL → Vector subprocess → validation
  - Uses real Vector binary as subprocess 
  - Isolated units that don't depend on vectordotdev bindings
  - Creates temporary Vector configs and runs Vector processes

### Integration Tests (`integration/`)  
**Component interaction testing - tests how parts work together**

- **Bindings Tests**: Test vectordotdev Python bindings directly
  - Uses `vector.Vector()` Python API
  - Tests regex2vrl integration with vectordotdev library
  - No subprocess calls - pure Python integration

### E2E Tests (`e2e/`)
**End-to-end production scenarios - full workflow testing**

- **Production Patterns**: Comprehensive testing with real-world patterns
- **Full Pipeline**: regex2vrl → VRL → Vector → validation → reporting
- **Performance Testing**: THG validation and optimization verification

## Production Patterns Tested

Based on 2025 research of most common patterns in production environments:

### Regex Patterns
1. **Apache Combined Log** - Most common web server log format
2. **Nginx Access Log** - Nginx with X-Forwarded-For support
3. **Syslog Standard** - RFC3164 syslog format
4. **JSON Application Log** - Structured application logs
5. **Docker Container Log** - Docker JSON log driver format
6. **Kubernetes Pod Log** - CRI-O/containerd format
7. **IP Address Extraction** - IPv4 address parsing
8. **ISO 8601 Timestamp** - Standard timestamp format
9. **Log Level Extraction** - Common log levels
10. **HTTP Status Code** - HTTP response codes

### Grok Patterns  
1. **COMBINEDAPACHELOG** - Apache combined log format
2. **COMMONAPACHELOG** - Apache common log format
3. **SYSLOGBASE** - Basic syslog structure
4. **SYSLOG5424PRI** - RFC5424 with priority
5. **Nginx Access** - Detailed nginx parsing
6. **HAProxy HTTP** - Load balancer logs
7. **AWS ELB** - Elastic Load Balancer logs
8. **MySQL Error** - Database error logs
9. **Postfix SMTP** - Mail server logs
10. **ISO 8601 Timestamp** - Grok timestamp parsing

## Running Tests

### Quick Start - All Tests
```bash
# Run all test categories
cd vectordotdev/tests
python run_tests.py

# Verbose output
python run_tests.py --verbose

# With custom Vector binary
python run_tests.py --vector-binary /path/to/vector
```

### By Test Category

```bash
# Unit tests only (isolated components)
python run_tests.py --category unit --verbose

# Integration tests only (vectordotdev bindings)
python run_tests.py --category integration --verbose

# E2E tests only (production scenarios)
python run_tests.py --category e2e --verbose

# Filtered E2E tests
python run_tests.py --category e2e --filter apache --verbose
```

### Individual Test Runners

```bash
# Run unit tests directly
python unit/subprocess.py --verbose --vector-binary /path/to/vector

# Run integration tests directly  
python integration/bindings.py --verbose

# Run E2E tests directly
python e2e/production_patterns.py --verbose --filter regex
```

## Test Requirements

### Prerequisites

1. **Python Dependencies**:
   ```bash
   pip install pytest pyyaml
   ```

2. **vectordotdev Library**: Must be in Python path
   ```bash
   # Automatically handled by test runners
   ```

### Optional (for full testing):

3. **Vector Binary**: For subprocess unit tests and E2E tests
   ```bash
   # Build Vector (from vector directory)
   cargo build --release
   # Or specify path: --vector-binary /path/to/vector
   ```

4. **vectordotdev Bindings**: For integration tests
   ```bash
   # Must be built and available as Python module
   ```

## Test Types Explained

### 🔧 Unit Tests
- **Purpose**: Test individual components in isolation
- **No Mocks**: Uses real Vector subprocess calls
- **Isolated**: Each test is independent
- **Fast**: Quick execution, focused testing

**Example**: Test that regex pattern `(?P<ip>\d+\.\d+\.\d+\.\d+)` converts to VRL that correctly extracts IP addresses when run through Vector subprocess.

### 🔗 Integration Tests  
- **Purpose**: Test component interactions
- **Bindings**: Uses vectordotdev Python bindings directly
- **Integration**: Tests how regex2vrl integrates with Vector
- **No Subprocesses**: Pure Python API usage

**Example**: Test that `vector.Vector(config)` with regex2vrl-generated VRL correctly processes log data through the Python API.

### 🚀 E2E Tests
- **Purpose**: Full production scenarios
- **Comprehensive**: Tests complete workflows
- **Performance**: Validates THG metrics
- **Real Data**: Uses actual production log patterns

**Example**: Test that Apache combined log parsing achieves 350+ THG performance with 100% parsing accuracy across 50 real log samples.

## Test Configuration

All patterns and test data are externalized (no hardcoding):

### Pattern Definitions (`fixtures/test_patterns/`)
```yaml
apache_combined_log:
  name: "Apache Combined Log Format"
  pattern: '^(?P<ip>\d+\.\d+\.\d+\.\d+)...'
  expected_fields: [ip, method, status]
```

### Test Data (`fixtures/test_data/`)
```yaml
apache_combined_log:
  - '192.168.1.100 - - [15/Jan/2025:10:30:45 +0000] "GET /index.html HTTP/1.1" 200 1024...'
```

### Test Configuration (`fixtures/test_configs/`)
```yaml
apache_combined_regex:
  pattern_file: "production_regex_patterns.yaml"
  pattern_key: "apache_combined_log"
  sample_data_file: "production_log_samples.yaml"
  performance_target_thg: 300
```

## Expected Output

Successful test run shows:

```
🧪 vectordotdev Test Suite
========================================

🔧 Running Unit Tests
==============================
📋 VRL Function Tests:
✅ 12/12 VRL expressions validated
✅ VRL Functions: Available

🔄 Vector Subprocess Unit Tests:
✅ Subprocess unit tests passed

🔗 Running Integration Tests
===================================
✅ Integration tests passed

🚀 Running End-to-End Tests
================================
✅ E2E tests passed

📊 Test Summary
====================
Unit: ✅ PASSED
Integration: ✅ PASSED  
E2E: ✅ PASSED

Overall: 3/3 categories passed (100%)
```

## Adding New Tests

### Adding Unit Tests
```python
# In unit/ directory
def test_new_pattern():
    pattern = "(?P<field>\w+)"
    converter = RegexToVRL()
    vrl = converter.convert(pattern)
    # Test with subprocess Vector call
```

### Adding Integration Tests  
```python  
# In integration/ directory
async def test_new_integration():
    vector_instance = vector.Vector(config)
    await vector_instance.start()
    # Test with vectordotdev bindings
```

### Adding E2E Tests
```yaml
# Add to fixtures/test_patterns/
new_pattern:
  name: "New Pattern"
  pattern: "regex_here" 
  expected_fields: [field1, field2]
```

## Troubleshooting

### Common Issues

1. **Vector binary not found** (Unit/E2E tests):
   ```bash
   # Build Vector or specify path
   --vector-binary /path/to/vector
   ```

2. **vectordotdev import error** (Integration tests):
   ```bash
   # Ensure vectordotdev library is built and available
   ```

3. **Tests timeout**: Increase timeout in test configuration

4. **Path issues**: Tests automatically handle relative paths from test runners

### Debug Mode
```bash
# Keep temporary files for debugging  
python unit/subprocess.py --keep-workspace --verbose
python e2e/production_patterns.py --keep-workspace --verbose
```

This organized structure ensures clear separation of concerns and follows testing best practices! 🎯