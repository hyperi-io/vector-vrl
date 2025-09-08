# VECTOR.md - Vector Core Data Processing Engine

**Stage 1 of the 4-component architecture**

## 🎯 **Purpose**

The `/vector` directory contains the upstream Vector data processing engine - the core component that provides high-performance log and metrics processing capabilities.

## 🏗️ **Role in Build Pipeline**

```
/vector (Stage 1) → /vector-bindings (Stage 2) → /vectordotdev (Stage 3)
                                                        ↑
                              /build (Orchestrator) ────┘
```

**Position**: **Foundation layer** - provides core Vector functionality  
**Dependencies**: None (upstream source)  
**Dependents**: vector-bindings, vectordotdev (via build system)  
**Build**: Managed by `/build` with auto-version detection

## 🔄 **Auto-Version Management**

Vector is **automatically updated** by the build system:

### **Version Detection**
- 🌐 **GitHub API Integration**: Auto-detects latest stable releases
- 🔄 **Progressive Fallback**: v0.49.0 → v0.48.0 → v0.47.0 on compatibility issues  
- 🎯 **Future-Proof**: Will work with v0.60.0+ automatically when released
- ⚡ **Smart Caching**: Avoids rebuilds when Vector version unchanged

### **Configuration Options**
```bash
# Environment variables (NO hardcoded values)
export VECTORDOTDEV_VECTOR_VERSION=v0.49.0     # Override auto-detection
export VECTORDOTDEV_MIN_VERSION=0.47.0         # Minimum compatible version
export VECTORDOTDEV_MAX_VERSION=1.0.0          # Maximum compatible version  
export SKIP_VECTOR_UPDATE=1                    # Skip version updates for speed
```

## 📁 **Directory Structure**

```
/vector/
├── src/                    # Vector Rust source code
├── lib/                    # Vector library components
├── target/                 # Build artifacts (auto-generated)
│   ├── release/           # Release build artifacts  
│   └── debug/             # Debug build artifacts
├── Cargo.toml             # Vector dependencies (managed by upstream)
├── Cargo.lock             # Dependency lock file
└── README.md              # Vector documentation
```

## ⚙️ **Build Process**

### **Automated by Build System**
The `/build` system handles all Vector operations:

```bash
# Automatic Vector management
./build/build --verbose                 # Auto-detect and build latest Vector
./build/build --test-flow              # Test Vector detection without building  
./build/build --skip-vector            # Skip Vector build (use existing)
```

### **Manual Vector Management** (Advanced)
```bash
# Manual Vector operations (not recommended)
cd vector && cargo build --release     # Build Vector directly
cd vector && cargo clean               # Clean Vector artifacts
```

## 🎯 **Integration Points**

### **For vector-bindings**
Vector provides compiled libraries that vector-bindings links against:
- `/vector/target/release/libvector.rlib` - Core Vector libraries
- `/vector/target/release/deps/` - Vector dependencies
- Vector Rust API surface for bindings integration

### **For vectordotdev**  
Vector functionality accessed through vector-bindings layer:
- VRL (Vector Remap Language) processing
- Data transformation pipelines
- Sink/source component integration

## 📊 **Build Monitoring**

The build system monitors Vector compilation:

### **Intelligent Detection**
- 🔍 **Phase Recognition**: Automatically detects Vector build phases
- ⏰ **Smart Timeouts**: No fixed timeouts - monitors actual progress
- 🔧 **Error Classification**: Distinguishes upstream vs code issues
- 🛠️ **Auto-Remediation**: Automatic fixes for common Vector build issues

### **Build Artifacts**
- **Success Indicators**: Build completion status and artifact counts
- **Performance Metrics**: Build time tracking and optimization
- **Cache Management**: Intelligent caching of Vector build artifacts
- **Failure Analysis**: Detailed logs for debugging build issues

## 🚨 **Upstream Issue Handling**

The build system handles upstream Vector issues automatically:

### **Common Issues**
- **krb5-src compilation**: Automatically detected and handled
- **protobuf compatibility**: Version conflicts resolved  
- **System dependency issues**: Automatic remediation where possible
- **Network timeouts**: Retry logic with exponential backoff

### **Fallback Strategy**  
When latest Vector has upstream issues:
1. **Auto-Detection**: Build system recognizes upstream vs code problems
2. **Version Fallback**: Automatically tries previous stable versions
3. **Issue Reporting**: Logs upstream issues for investigation  
4. **Continue Building**: Doesn't block development on upstream issues

## 🛡️ **Read-Only Philosophy**

**Critical Design Principle**: Vector directory is treated as **completely READ-ONLY**

### **No Modifications**
- ❌ No changes to Vector source code
- ❌ No custom patches or modifications  
- ❌ No vendor-specific customizations
- ✅ Pure upstream Vector integration

### **Benefits**
- 🔄 **Easy Updates**: Seamless Vector version upgrades
- 🛡️ **Upstream Compatibility**: No merge conflicts on updates
- 📦 **Clean Separation**: Clear component boundaries
- 🧪 **Testing Integrity**: Tests run against actual Vector behavior

## 📋 **Status & Monitoring**

### **Current Status**
- **Version**: Auto-detected from GitHub API
- **Build Status**: Monitored by build system  
- **Integration**: Linked by vector-bindings
- **Testing**: Validated by vectordotdev test suite

### **Health Checks**
```bash
# Check Vector build status
./build/build --test-flow

# Verify Vector artifacts
ls -la vector/target/release/

# Test Vector functionality  
./vector/target/release/vector --version
```

## 🔧 **Development Guidelines**

### **When Working with Vector**
1. **Never modify** Vector source code directly
2. **Use build system** for all Vector operations
3. **Test changes** with multiple Vector versions  
4. **Report upstream issues** but don't patch locally

### **Integration Development**
1. **Add features** in vector-bindings layer, not Vector
2. **Use Vector APIs** through proper Rust interfaces
3. **Follow Vector conventions** for configuration and data flow
4. **Test compatibility** across Vector versions

---

**Vector provides the foundation** for the entire vectordotdev project - it's the high-performance data processing engine that makes everything possible. The build system ensures this foundation stays current and compatible with the rest of the stack.