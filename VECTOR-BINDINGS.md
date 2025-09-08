# VECTOR-BINDINGS.md - Rust Bindings Intermediate Layer

**Stage 2 of the 4-component architecture**

## 🎯 **Purpose**

The `/vector-bindings` directory provides a **Rust intermediate layer** that creates clean, safe interfaces between Vector core components and Python bindings.

## 🏗️ **Role in Build Pipeline**

```
/vector (Stage 1) → /vector-bindings (Stage 2) → /vectordotdev (Stage 3)
                           ↑
           /build (Orchestrator) manages dependencies and builds
```

**Position**: **Interface layer** - bridges Vector and Python  
**Dependencies**: Vector core (`/vector` build artifacts)  
**Dependents**: vectordotdev Python bindings  
**Build**: Stage 2 of 3-stage build system

## 🎨 **Design Philosophy**

### **Clean Separation of Concerns**
- **Vector Integration**: Uses Vector components without modification
- **Safe Rust Interface**: Provides memory-safe access to Vector functionality  
- **Python Preparation**: Prepares Vector APIs for PyO3 binding generation
- **Error Handling**: Rust error types that translate cleanly to Python exceptions

### **Read-Only Vector Principle**
- 🔗 **Links Against Vector**: Uses compiled Vector artifacts from `/vector/target/`
- 📦 **No Vector Modifications**: Maintains upstream compatibility
- ⚙️ **Build-Time Integration**: Dependencies resolved during build
- 🔄 **Auto-Sync**: Build system syncs Vector versions automatically

## 📁 **Directory Structure**

```
/vector-bindings/
├── src/
│   └── lib.rs              # PyO3 bindings implementation (ALL Rust code)
├── vector_deps.toml        # Auto-detection configuration (NO hardcoded versions)
├── build.rs                # Build-time Vector version detection  
├── Cargo.toml              # Rust dependencies + PyO3 (auto-managed)
├── Cargo.lock              # Dependency lock (auto-generated)
└── target/                 # Compiled Python extension (.so/.dll files)
```

**Key Point**: `/vector-bindings` contains **ALL Rust code** including PyO3 bindings. The `/vectordotdev` directory should contain **ONLY Python code** that imports the compiled bindings.

## ⚙️ **Auto-Detection Configuration**

**`vector_deps.toml`** - Zero hardcoded values:
```toml
[vector_integration]
auto_detect_version = true
auto_detect_fallback_count = 3  
github_api_url = "https://api.github.com/repos/vectordotdev/vector/releases"
vector_repo_url = "https://github.com/vectordotdev/vector.git"

# All configurable via environment variables:
# VECTORDOTDEV_MIN_VERSION, VECTORDOTDEV_MAX_VERSION, etc.
```

## 🔧 **Build System Integration**

### **Stage 2 Build Process**
1. **Dependency Sync**: Build system syncs Vector version from Stage 1
2. **Auto-Detection**: Detects Vector build artifacts and version
3. **Bindings Build**: Compiles Rust bindings against Vector libraries
4. **Interface Generation**: Creates clean APIs for Python layer

### **Build Commands**
```bash
# Build as part of 3-stage system (recommended)
./build/build --verbose

# Build vector-bindings only (requires Vector artifacts) 
cd vector-bindings && cargo build

# Test bindings integration
cd vector-bindings && cargo test
```

## 🛠️ **Current Implementation Status**

### ✅ **Working Components**
- **Config Parsing**: TOML/YAML configuration validation
- **Error Types**: Comprehensive error handling for Python integration
- **Basic Structure**: Foundation for Vector integration
- **Build Integration**: Auto-sync with Vector versions

### 🚧 **Development Areas**
- **Transform Pipeline**: VRL transform execution needs implementation
- **Data Flow**: Complete source→transform→sink pipeline
- **Vector API Integration**: Full Vector component access
- **Performance Optimization**: Zero-copy data handling

### 🎯 **Next Development Priorities**
1. **VRL Transform Execution**: Implement real transform pipeline
2. **Vector Component Integration**: Access Vector's source/sink registry
3. **Memory Management**: Optimize data flow between layers
4. **Error Propagation**: Detailed error context for Python layer

## 💻 **API Interface**

### **Rust API** (for vectordotdev integration)
```rust
// Core types provided to Python layer
pub struct VectorInstance {
    config: VectorConfig,
    runtime: Option<Runtime>,
    is_running: bool,
    pending_data: Vec<(String, Vec<u8>)>,
}

impl VectorInstance {
    pub fn new(config: VectorConfig) -> Result<Self, VectorBindingsError>;
    pub fn start(&mut self) -> Result<(), VectorBindingsError>;
    pub fn stop(&mut self) -> Result<(), VectorBindingsError>;
    pub fn send_data(&mut self, source_id: &str, data: Vec<u8>) -> Result<(), VectorBindingsError>;
}
```

### **Error Types** (mapped to Python exceptions)
```rust
#[derive(Debug, thiserror::Error)]
pub enum VectorBindingsError {
    #[error("Config validation failed: {0}")]
    ConfigValidation(String),
    
    #[error("Vector instance is already running")]
    AlreadyRunning,
    
    #[error("Vector instance is not running")]
    NotRunning,
    
    #[error("Invalid data: {0}")]
    InvalidData(String),
}
```

## 🔍 **Integration Testing**

### **Testing Strategy**
```bash
# Test bindings compilation
cd vector-bindings && cargo check

# Test with vectordotdev integration
PYTHONPATH=/projects/vectordotdev python vectordotdev/tests/integration/bindings.py
```

### **Validation Points**
- **Config Parsing**: TOML/YAML configuration validation
- **Vector Linking**: Successful compilation against Vector artifacts
- **Memory Safety**: No unsafe memory operations
- **Error Handling**: All error paths tested and documented

## 📊 **Performance Characteristics**

### **Current Status**
- **Compilation Time**: ~5-10 seconds when Vector artifacts available
- **Memory Usage**: Minimal overhead for interface layer
- **Latency**: Near-zero for basic operations
- **Throughput**: Limited by current stub implementation

### **Target Performance** (when fully implemented)
- **Transform Throughput**: Match Vector native performance
- **Memory Efficiency**: Zero-copy data paths where possible  
- **Startup Time**: Sub-second pipeline initialization
- **Error Recovery**: Fast failure detection and graceful degradation

## 🛡️ **Security Considerations**

### **Memory Safety**
- **Rust Guarantees**: All memory operations are safe by construction
- **No Unsafe Blocks**: Minimal use of `unsafe` code, well-documented when needed
- **Error Boundaries**: Rust errors don't propagate as crashes to Python
- **Resource Cleanup**: Automatic resource management with RAII

### **Data Isolation** 
- **No Shared State**: Each VectorInstance is isolated
- **Clean Interfaces**: Well-defined API boundaries
- **Error Isolation**: Failures in one instance don't affect others

## 🔧 **Development Guidelines**

### **When Working on Bindings**
1. **Maintain Vector Compatibility**: Don't break Vector integration
2. **Use Safe Rust**: Minimize unsafe code, document when necessary
3. **Test Memory Usage**: Check for leaks and excessive allocation
4. **Document APIs**: Clear documentation for Python integration layer

### **Integration Development**
1. **Follow Vector Patterns**: Use Vector's established patterns for components
2. **Error Handling**: Map Rust errors to appropriate Python exceptions
3. **Performance Focus**: Optimize data paths and minimize copying
4. **Version Compatibility**: Test across multiple Vector versions

### **Build System Integration**
1. **Auto-Detection**: Use build system's version detection
2. **Dependency Sync**: Let build system manage Vector dependencies  
3. **Clean Builds**: Support clean rebuilds when Vector changes
4. **Progress Monitoring**: Integrate with build system monitoring

## 📋 **Current Limitations**

### **Known Issues**
- **Transform Pipeline**: VRL transforms not fully implemented
- **Sink Integration**: Limited sink type support
- **Async Runtime**: Basic runtime management needs enhancement
- **Memory Optimization**: Data copying not yet optimized

### **Workarounds**
- **Use Subprocess Tests**: For full Vector functionality validation
- **Basic File Sinks**: Minimal file output capability available
- **Config Validation**: VRL syntax checking works correctly
- **Future Development**: Foundation ready for full implementation

## 🎯 **Roadmap**

### **Phase 1** (Current)
- ✅ Basic structure and config parsing
- ✅ Build system integration
- ✅ Error type definitions
- 🚧 Basic file sink implementation

### **Phase 2** (Next)  
- 🎯 VRL transform execution
- 🎯 Vector component registry access
- 🎯 Complete source→transform→sink pipeline
- 🎯 Performance optimization

### **Phase 3** (Future)
- 🎯 Advanced Vector features (enrichment, aggregation)
- 🎯 Custom component development  
- 🎯 Streaming and backpressure handling
- 🎯 Monitoring and observability integration

---

**vector-bindings serves as the crucial interface layer** that enables safe, high-performance Vector integration while maintaining clean separation between the upstream Vector engine and Python application code.