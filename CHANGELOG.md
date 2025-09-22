# Changelog

All notable changes to vectordotdev will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-01-15

### Added
- **🧪 Comprehensive Test Suite**: Complete test infrastructure for regex2vrl functionality
  - **Unit Tests**: Vector subprocess integration tests (no mocks) 
  - **Integration Tests**: vectordotdev Python bindings tests
  - **E2E Tests**: Production pattern validation with performance metrics
  - **100% Test Success Rate**: All unit tests passing with real Vector execution

- **📊 Production Pattern Coverage**: Research-based pattern testing
  - **Top 10 Regex Patterns**: Most common production log parsing patterns (2025 research)
  - **Top 10 Grok Patterns**: ELK stack patterns (COMBINEDAPACHELOG, SYSLOGBASE, etc.)
  - **Real Log Samples**: Authentic production log data for validation
  - **Configuration-Driven**: All patterns and data externalized to YAML files

- **⚡ Improved regex2vrl Converter**: Enhanced VRL code generation
  - **Fixed VRL Syntax**: Removed invalid `for` loops and `break` statements
  - **Better Type Safety**: Added proper `string!()` conversions for array access
  - **Robust IP Extraction**: Multi-strategy IP address parsing with 100% success rate
  - **Enhanced Timestamp Parsing**: Multi-format timestamp detection and conversion
  - **Improved Pattern Detection**: More accurate built-in parser classification

- **🏗️ Best Practices Test Structure**: Organized testing framework
  ```
  vectordotdev/tests/
  ├── unit/           # Isolated component tests (Vector subprocess)
  ├── integration/    # Component interaction tests (Python bindings)
  ├── e2e/           # End-to-end production scenarios
  └── fixtures/      # Shared test data and patterns (no hardcoding)
  ```

### Fixed
- **VRL Code Generation**: Fixed invalid VRL syntax in regex2vrl converter
  - Removed reserved keywords (`for`, `break`) causing compilation errors
  - Added proper type handling for array access (`string!(parts[0])`)
  - Fixed `replace()` function calls to use correct VRL syntax
- **Pattern Classification**: Improved built-in parser detection accuracy
  - IP patterns no longer misclassified as syslog
  - More conservative built-in parser usage for higher reliability
- **Test Infrastructure**: Resolved subprocess execution and temp file handling
  - Fixed Vector subprocess calls with proper data directory creation
  - Implemented proper cleanup and error handling
  - Added comprehensive debugging and validation tools

### Changed
- **Temp File Policy**: All tests now use `.tmp/` directory per project policy
- **Test Organization**: Migrated from ad-hoc testing to structured approach
- **Import Handling**: Improved module path resolution for regex2vrl library

### Technical Details
- **Vector Integration**: Tests validate actual Vector binary execution
- **Performance Validation**: THG performance metrics testing (300-350+ targets)  
- **Field Extraction**: Comprehensive validation of parsed log fields
- **Error Handling**: Graceful fallbacks and detailed error reporting
- **Documentation**: Updated STATE.md with test structure and usage examples

### Breaking Changes
None - this is a backward-compatible minor release.

## [0.1.0] - 2025-01-02

### Added
- Initial release with regex2vrl functionality
- Basic Vector Python bindings
- Core VRL conversion capabilities