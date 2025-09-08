# BUILD.md - Build Automation & Orchestration System

**Orchestrator for the 4-component architecture**

## 🎯 **Purpose**

The `/build` directory contains the **intelligent build automation system** that orchestrates the entire vectordotdev project compilation with auto-detection, monitoring, and progressive fallback capabilities.

## 🏗️ **Role in Build Pipeline**

```
                    /build (Orchestrator)
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
    │ /vector │────▶│ /vector-│────▶│/vector- │
    │(Stage 1)│     │bindings │     │ dotdev  │
    │         │     │(Stage 2)│     │(Stage 3)│
    └─────────┘     └─────────┘     └─────────┘
```

**Position**: **Orchestrator** - manages entire build lifecycle  
**Dependencies**: None (autonomous)  
**Manages**: All 3 stages with intelligent coordination  
**Features**: Auto-detection, monitoring, fallback, caching

## 📁 **Directory Structure**

```
/build/
├── build_system.py         # Main orchestrator with CLI interface
├── core_build.py           # 3-stage build execution engine
├── vector_detection.py     # Vector version auto-detection  
├── dependency_sync.py      # Cross-component dependency synchronization
├── monitoring.py           # Intelligent build progress monitoring
├── common.py               # Shared types and utilities
├── build                   # Build launcher script
├── pyproject.toml          # Build system dependencies
├── .venv/                  # Isolated Python environment
├── vector_deps.toml        # Version detection configuration (no hardcoded values)
└── README.md               # Build system documentation
```

## 🚀 **Quick Usage**

```bash
# Run complete 3-stage build with auto-detection
./build/build --verbose

# Test build flow without heavy compilation
./build/build --test-flow  

# Skip Vector build (test stages 2-3 only)
./build/build --skip-vector

# Clean build with fresh detection
./build/build --clean
```

## ⚙️ **3-Stage Build System**

### **Stage 1: Vector Core**
```bash
[09:51:39] 🚀 Building Vector core v0.49.0
[09:51:46] 📊 Monitoring Vector Core with intelligent detection...
[09:55:02] ✓ compiling completed in 194.6s
```

**Responsibilities**:
- 🔍 **Auto-detect** latest compatible Vector version via GitHub API  
- 📥 **Download & Extract** Vector source from GitHub releases
- 🛠️ **Build Vector** with required features for bindings integration
- 📊 **Monitor Progress** with phase detection (compiling, linking, etc.)
- 🔄 **Handle Failures** with automatic fallback to older versions

### **Stage 2: Vector Bindings**
```bash
[09:51:27] 🔄 Syncing vector-bindings deps with Vector v0.49.0...
[09:51:27] ✅ Synced 8 dependencies with Vector v0.49.0
```

**Responsibilities**:
- 🔄 **Sync Dependencies** from Vector to vector-bindings Cargo.toml
- 🔗 **Link Against Vector** build artifacts from Stage 1
- 🛠️ **Build Rust Bindings** intermediate layer  
- ✅ **Validate Integration** between Vector and bindings

### **Stage 3: Python Bindings**  
```bash
[09:51:27] 🔄 Building vectordotdev Python bindings...
[09:51:27] ✅ Python layer compilation successful
```

**Responsibilities**:
- 🔗 **Link Against Bindings** from Stage 2
- 🐍 **Build PyO3 Extension** for Python integration
- 📦 **Create Python Wheel** for distribution
- 🧪 **Run Test Validation** with real Vector integration

## 🌐 **Auto-Detection System**

### **Version Detection Pipeline**
```python
# NO hardcoded versions anywhere
class VectorVersionDetector:
    def __init__(self):
        # All configurable via environment variables
        self.github_api_url = os.getenv('VECTORDOTDEV_GITHUB_API_URL', 'https://api.github.com/...')
        self.fallback_count = int(os.getenv('VECTORDOTDEV_FALLBACK_COUNT', '3'))
        self.timeout = int(os.getenv('VECTORDOTDEV_VERSION_TIMEOUT', '10'))
```

#### **Detection Process**
1. 🌐 **Web Fetch**: GitHub API for latest stable releases
2. 🔍 **Version Filtering**: Semantic versioning validation (x.y.z)
3. 📋 **Compatibility Check**: Min/max version constraints (if configured)
4. 🎯 **Future Proof**: Automatically works with Vector v0.60+ when released

#### **Configuration Options**
```bash
# Environment variable overrides (NO hardcoded defaults)
export VECTORDOTDEV_VECTOR_VERSION=v0.49.0      # Override auto-detection
export VECTORDOTDEV_MIN_VERSION=0.47.0          # Minimum compatible 
export VECTORDOTDEV_MAX_VERSION=1.0.0           # Maximum compatible
export VECTORDOTDEV_GITHUB_API_URL=https://...   # Custom API endpoint
export VECTORDOTDEV_FALLBACK_COUNT=5            # Fallback version count
```

## 📊 **Intelligent Monitoring**

### **Build Progress Detection**
The monitoring system uses **intelligent detection** instead of fixed timeouts:

#### **Phase Recognition**
```python
# Automatically detects Vector build phases
"Compiling proc-macro2" → "compiling" phase
"Linking vector" → "linking" phase  
"error: compilation failed" → "error" phase
"Finished release" → "completion" phase
```

#### **Smart Timeouts**
- ⏰ **No Fixed Timeouts**: Monitors actual progress instead
- 📈 **File Growth Tracking**: Detects stalled vs active compilation
- 🔄 **Adaptive Monitoring**: Adjusts based on build phase
- 💥 **Error Classification**: Distinguishes upstream vs code issues

### **Progress Reporting**
```
[09:51:48]   → Compiling serde v1.0.219
[09:51:48]   📋 Entering compiling phase...
[09:52:30]   ✓ compiling completed in 194.6s
[09:52:30]   📋 Entering error phase...
[09:52:31]   ⚠️ Detected upstream issue: krb5-src compilation failure
```

## 🔄 **Progressive Fallback System**

### **Automatic Version Fallback**
When builds fail, the system intelligently tries older versions:

```bash
# Fallback sequence (auto-detected, no hardcoding)
🔄 Attempt 1: v0.49.0  → Upstream issue detected
🔄 Attempt 2: v0.48.0  → Build successful  
✅ Using Vector v0.48.0
```

#### **Error Classification**
```python
class ErrorType(Enum):
    UPSTREAM_COMPILE = "upstream_compile"      # Try older version
    VECTOR_CORE_FAILURE = "vector_core_failure"   # Try older version  
    OUR_CODE_FAILURE = "our_code_failure"         # Don't retry, fix code
    DEPENDENCY_FAILURE = "dependency_failure"     # Auto-remediation
```

#### **Smart Decision Making**
- 🧠 **Upstream vs Code**: Distinguishes Vector issues from project issues
- 🔄 **Retry Logic**: Only retries on upstream/compatibility issues
- 🛑 **Fail Fast**: Stops on code issues that retrying won't fix
- 📋 **Detailed Logging**: Comprehensive error analysis for debugging

## 🛠️ **Build Commands**

### **Primary Interface**
```bash
# Complete build with auto-detection  
./build/build

# Verbose build with detailed progress
./build/build --verbose

# Test flow without heavy compilation
./build/build --test-flow

# Skip Vector build (use existing)
./build/build --skip-vector  

# Clean all artifacts and rebuild
./build/build --clean
```

### **Python API** (Internal)
```bash
# Direct Python execution (used by build launcher)
build/.venv/bin/python build/build_system.py --verbose
build/.venv/bin/python build/vector_detection.py --latest
build/.venv/bin/python build/dependency_sync.py vector-bindings
```

## 🎯 **Configuration Management**

### **Environment Variables**
All behavior configurable via environment variables:

#### **Build Control**
- `VECTORDOTDEV_VERBOSE=true` - Verbose build output
- `SKIP_VECTOR_UPDATE=1` - Skip Vector version detection  
- `UPDATE_DEPENDENCIES=1` - Force dependency updates
- `VECTORDOTDEV_TEMP_DIR=/custom/path` - Custom temp directory

#### **Vector Version Management**  
- `VECTORDOTDEV_VECTOR_VERSION=v0.49.0` - Override auto-detection
- `VECTORDOTDEV_MIN_VERSION=0.47.0` - Minimum version constraint
- `VECTORDOTDEV_MAX_VERSION=1.0.0` - Maximum version constraint
- `VECTORDOTDEV_FALLBACK_COUNT=3` - Number of fallback versions

#### **Performance Tuning**
- `VECTORDOTDEV_BUILD_TIMEOUT=1800` - Maximum build time (30 min)
- `VECTORDOTDEV_DOWNLOAD_TIMEOUT=900` - Download timeout (15 min)  
- `VECTORDOTDEV_PARALLEL_JOBS=8` - Cargo parallel jobs
- `RUSTFLAGS="-C linker=gcc"` - Rust compiler flags

### **Configuration Files**
```bash  
# Build system config (auto-detected values only)
build/vector_deps.toml      # Version detection settings
vector-bindings/vector_deps.toml  # Bindings-specific config
```

## 📈 **Performance Optimization**

### **Build Caching**
- **Git LFS Integration**: Cache large build artifacts
- **Smart Cache Keys**: Based on Cargo.toml + config changes
- **Incremental Builds**: Only rebuild changed components  
- **Parallel Compilation**: Multi-core build acceleration

### **Monitoring Efficiency** 
- **File Growth Tracking**: No polling - uses filesystem events
- **Phase Detection**: Minimal overhead progress tracking
- **Memory Usage**: Efficient monitoring without bloating builds
- **Error Analysis**: Fast upstream issue classification

## 🛡️ **Error Handling & Recovery**

### **Upstream Issue Detection**
Automatically detects and handles Vector upstream issues:
- **krb5-src compilation failures**: Known upstream issue, auto-fallback
- **protobuf API changes**: Detects and adapts to Vector updates
- **System dependency conflicts**: Auto-remediation where possible
- **Network timeouts**: Exponential backoff with retry logic

### **Auto-Remediation**
```bash
# Automatic fixes applied during build
⚠️ Detected upstream issue: krb5-src compilation failure  
🔄 Auto-fallback: Trying Vector v0.48.0...
✅ Build successful with Vector v0.48.0
```

### **Build Recovery**
- **Partial Build Recovery**: Resume from successful stages
- **Dependency Repair**: Automatic dependency conflict resolution
- **Cache Restoration**: Restore working builds from cache
- **Clean Rebuild**: Full rebuild when corruption detected

## 🧪 **Integration with Testing**

### **Test Execution Integration**
```bash
# Build system can run tests automatically
./build/build --run-tests

# Test validation after successful build  
RUN_TESTS=1 ./build/build --verbose

# Performance validation
./build/build && cd vectordotdev/tests && python run_tests.py --category e2e
```

### **Test Data Management**
- **Pattern Sync**: Keeps test patterns updated with latest Vector features
- **Sample Data**: Maintains real-world log samples for validation
- **Performance Baselines**: Tracks THG performance across Vector versions

## 🔧 **Development Workflow**

### **Standard Development Process**
1. **Make Changes**: Modify any component (vector-bindings, vectordotdev, etc.)
2. **Run Build**: `./build/build --verbose` (auto-detects dependencies)
3. **Validate**: Build system runs appropriate stage rebuilds
4. **Test**: `cd vectordotdev/tests && python run_tests.py`
5. **Commit**: Changes are validated and ready

### **Advanced Scenarios**
```bash
# New Vector version available - automatic detection and integration
./build/build  # Auto-detects v0.60.0, downloads, builds, tests

# Working on vector-bindings - only rebuild affected stages  
./build/build --skip-vector  # Skips Stage 1, rebuilds Stages 2-3

# Testing new patterns - validate with real Vector
cd vectordotdev/tests && python unit/test_regex2vrl_subprocess.py --verbose
```

## 📋 **Build System Status**

### ✅ **Working Features**
- **3-Stage Pipeline**: vector → vector-bindings → vectordotdev
- **Auto-Version Detection**: GitHub API integration with web fetch
- **Progressive Fallback**: 3 version fallback on upstream issues  
- **Dependency Synchronization**: Auto-sync between stages
- **Intelligent Monitoring**: Progress detection without fixed timeouts
- **Error Classification**: Upstream vs code issue detection

### 🚧 **Development Areas**
- **Transform Pipeline**: vector-bindings Stage 2 VRL execution
- **YAML Config Support**: Preferred format (TOML deprecated with vector.dev)
- **Performance Optimization**: Build time and artifact caching
- **CI/CD Integration**: Re-enable GitHub Actions workflows

## 🎯 **Troubleshooting**

### **Common Build Issues**

#### **Vector Download Failures**
```bash
❌ Network error: GitHub API timeout
🔄 Solution: Check internet connection, retry with --verbose
```

#### **Compilation Failures**  
```bash
❌ Upstream issue: krb5-src compilation failure
🔄 Solution: Build system auto-fallback to previous Vector version
```

#### **Dependency Conflicts**
```bash
❌ Dependency failure: Version conflict detected
🔄 Solution: Build system auto-sync resolves conflicts
```

### **Debug Commands**
```bash
# Test detection without building
./build/build --test-flow

# Check Vector version detection
python build/vector_detection.py --latest

# Validate dependency sync
python build/dependency_sync.py vector-bindings

# Monitor build progress manually  
python build/monitoring.py --debug
```

## 📊 **Build Performance**

### **Typical Build Times**
- **Vector Core (Stage 1)**: 3-5 minutes (full build)
- **Vector Bindings (Stage 2)**: 30 seconds (when Vector artifacts available)  
- **vectordotdev (Stage 3)**: 1-2 minutes (PyO3 compilation)
- **Total**: 4-7 minutes for complete build

### **Optimization Features**
- **Artifact Reuse**: Stage 1 artifacts cached for Stages 2-3
- **Incremental Builds**: Only rebuild changed components
- **Parallel Compilation**: Multi-core acceleration  
- **Smart Caching**: Git LFS integration for large artifacts

## 🌐 **Future-Proof Design**

### **Automatic Compatibility**
The build system is designed to work with **any future Vector release**:

```python
# When Vector v0.60.0 is released
./build/build  # Automatically detects, downloads, builds, tests v0.60.0
```

#### **Version Compatibility Strategy**
- 🔍 **API Stability Detection**: Monitors Vector API changes
- 🔄 **Automatic Adaptation**: Adjusts build flags for new Vector versions
- 📋 **Compatibility Testing**: Validates each stage with new versions
- 🛠️ **Graceful Degradation**: Falls back on compatibility issues

### **Configuration Evolution**
- **No Breaking Changes**: Build system evolves without breaking existing workflows
- **Backward Compatibility**: Old environment variables continue working
- **Forward Compatibility**: Ready for future Vector features
- **Auto-Migration**: Automatic migration of old configuration formats

---

**The build system provides the intelligence** that keeps vectordotdev current, compatible, and building successfully across Vector releases while maintaining clean component separation and comprehensive validation.