# PROJECT STRUCTURE - Multi-Component Architecture

**CRITICAL**: Read FIRST before working on any component.

## 4-Component Dependencies
**ORDER**: `vector` → `vector-bindings` → `vectordotdev` ← `build`

```
/projects/vectordotdev/
├── vector/             # 1: Upstream Vector (Read-Only)
├── vector-bindings/    # 2: Rust PyO3 Bindings  
├── vectordotdev/       # 3: Python Package
└── build/              # 4: Build Orchestration
```

## Component Details

### 1. `/vector/` (Upstream - Read Only)
- **Purpose**: Core Vector engine (Rust)
- **Dependencies**: None (self-contained)
- **Produces**: `target/release/deps/*.rlib`, `target/release/vector`
- **Work Dir**: `cd /projects/vectordotdev/vector`
- **Command**: `cargo build --release`

### 2. `/vector-bindings/` (PyO3 Rust Bindings)
- **Purpose**: Rust → Python FFI
- **Dependencies**: Vector libraries from `../vector/target/release/`
- **Produces**: `target/wheels/*.whl`, `*.so` files
- **Work Dir**: `cd /projects/vectordotdev/vector-bindings`
- **Command**: `maturin develop`

### 3. `/vectordotdev/` (Python Package)
- **Purpose**: Python API + regex2vrl tools
- **Dependencies**: Vector bindings (testing only), regex2vrl (standalone)
- **Produces**: PyPI wheel with bundled bindings
- **Work Dir**: `cd /projects/vectordotdev/vectordotdev`
- **Command**: `PYTHONPATH=src python tests/run_tests.py`

### 4. `/build/` (Orchestration)
- **Purpose**: 3-stage build automation
- **Dependencies**: Orchestrates all other components
- **Produces**: Integrated builds and releases
- **Work Dir**: `cd /projects/vectordotdev/build`
- **Command**: `python build_system.py`

---

## File Dependencies Flow

### Stage 1: Vector → .rlib files
```
vector/Cargo.toml                    → vector/target/release/deps/*.rlib
vector/src/**/*.rs                   → vector/target/release/vector
```

### Stage 2: Vector-Bindings → .so/.whl files  
```
vector/target/release/deps/*.rlib    → [Links into vector-bindings]
vector/Cargo.toml workspace.deps     → vector-bindings/Cargo.toml [SYNC]
vector-bindings/src/lib.rs           → vector-bindings/target/wheels/*.whl
                                     → vector_bindings.*.so files
```

### Stage 3: VectorDotDev → PyPI package
```
vector_bindings.*.so                 → vectordotdev/src/vectordotdev/_bindings/
vectordotdev/src/vectordotdev/regex2vrl/ → STANDALONE (no deps)
vectordotdev/tests/                  → Uses bindings for VRL validation only
```

### Stage 4: Build System → Orchestration
```
build/vector_detection.py            → Auto-detects Vector versions
build/dependency_sync.py             → Syncs Vector → vector-bindings deps
build/core_build.py                  → Executes 3-stage sequence
```

## Critical Rules (DO NOT VIOLATE)

### Work Directory Rules
1. **Always `cd` to component directory** before working
2. **Never run cross-component commands** from root
3. **Respect component boundaries** - don't edit other components

### Dependency Rules  
4. **regex2vrl is standalone** - no Vector deps in core code
5. **Bindings for testing only** - used to validate generated VRL
6. **Build order matters** - follow: vector → vector-bindings → vectordotdev
7. **Use PYTHONPATH=src** for vectordotdev testing

### Common Pitfalls
❌ Working from project root  
✅ `cd vectordotdev && PYTHONPATH=src python tests/run_tests.py`

❌ Adding Vector bindings to regex2vrl code  
✅ Keep regex2vrl standalone, use bindings in tests only

❌ Building everything at once  
✅ Follow 3-stage: vector → vector-bindings → vectordotdev

❌ Editing vector/ source (read-only upstream)  
✅ Work in vector-bindings/ or vectordotdev/ only

## Quick Commands
```bash
# Vector (rarely needed)
cd /projects/vectordotdev/vector && cargo build --release

# Rust bindings  
cd /projects/vectordotdev/vector-bindings && maturin develop

# Python package (most common)
cd /projects/vectordotdev/vectordotdev && PYTHONPATH=src python tests/run_tests.py

# Build system
cd /projects/vectordotdev/build && python build_system.py
```