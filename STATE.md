# vectordotdev Project State Guide

**🚨 READ FIRST**: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) + [TODO.md](TODO.md)

## AI Assistant Compatibility
This guide works with: **Cursor**, **Claude Code**, **Claude.ai**, **ChatGPT**, and other AI coding assistants.

## Project Core
Python extension (Rust) for **native Vector execution** - no subprocess, direct PyO3 integration.

**Goals**: YAML/TOML config → in-process Vector → native errors → THG benchmarking

## Session Rules (All AI Assistants)
1. Read [TODO.md](TODO.md) for current tasks
2. Work in component dirs (see PROJECT_STRUCTURE.md)  
3. Track progress by updating TODO.md
4. Use component isolation: `cd vectordotdev && PYTHONPATH=src`

## Status (v1.0.5)
- ✅ **Build System**: 3-stage (Vector→Bindings→Python), auto-detection, JFrog PyPI
- ✅ **regex2vrl**: Standalone VRL generator, 100% unit tests, production-ready  
- ⚠️ **Native Integration**: PyO3 bindings available, Vector runtime binding in progress

## Key Features
- **regex2vrl**: Standalone VRL code generator (no Vector deps)
- **Production patterns**: Apache, Nginx, Docker, K8s, JSON, Syslog, AWS ELB, MySQL
- **THG benchmarking**: 350+ performance targets with built-in parsers
- **Native execution**: PyO3 bindings for in-process Vector processing

## Commands

### Work Directories (CRITICAL)
```bash
# Vector (rarely needed)
cd /projects/vectordotdev.standalone/vector && cargo build --release

# Rust bindings  
cd /projects/vectordotdev.standalone/vector-bindings && maturin develop

# Python package (most common)
cd /projects/vectordotdev.standalone/vectordotdev && PYTHONPATH=src python tests/run_tests.py

# Build system
cd /projects/vectordotdev.standalone/build && python build_system.py
```

### Quick Tasks
- **regex2vrl**: `cd vectordotdev && PYTHONPATH=src python -c "from vectordotdev.regex2vrl import RegexToVRL"`
- **Testing**: `cd vectordotdev && PYTHONPATH=src python tests/run_tests.py --category unit`
- **Build**: `cd build && python build_system.py --verbose`

## Architecture Summary  
See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for complete details:
- 4-component dependency flow: vector → vector-bindings → vectordotdev ← build
- File flows: .rlib → .so → wheels → PyPI package  
- Component isolation and work directory rules

## Critical Rules
- **Component isolation**: Always `cd` to specific component directory before work
- **regex2vrl standalone**: No Vector dependencies in core code, only in tests  
- **Python paths**: Use `PYTHONPATH=src` for vectordotdev testing
- **Build order**: vector → vector-bindings → vectordotdev (dependencies flow)
- **No hardcoding**: Use dynaconf for configuration, `./.tmp/` for temp files

## regex2vrl Status (CRITICAL)
**PRODUCTION READY** - 100% unit test pass rate, standalone VRL generator

**Current Status**:
- ✅ Standalone module (no Vector deps in core)
- ✅ Real Vector validation via subprocess  
- ✅ Apache, Nginx, Docker, K8s, JSON, Syslog patterns working
- ✅ THG performance targets 350+ with built-in parsers
- ⚠️ 2 patterns need optimization: HAProxy HTTP, Postfix SMTP

**Key Files**:
- `src/vectordotdev/regex2vrl/core.py` - Main RegexToVRL class
- `src/vectordotdev/regex2vrl/working_vrl_engine.py` - VRL generation engine
- `src/vectordotdev/regex2vrl/grok_converter.py` - GrokToVRL class

## Build System Status (CRITICAL)
**3-Stage Architecture**: vector → vector-bindings → vectordotdev ← build

**Current State**:
- ✅ Stage 1 (Vector): Auto-detection, progressive fallback working
- ✅ Stage 2 (Bindings): Dependency sync, 2.0s builds working  
- ⚠️ Stage 3 (Python): Needs investigation - maturin develop failures

**Key Components**:
- `build/vector_detection.py` - Auto-detects Vector versions via GitHub API
- `build/dependency_sync.py` - Syncs Vector → vector-bindings Cargo.toml
- `build/core_build.py` - 3-stage execution engine
- `build/monitoring.py` - Intelligent build progress tracking

## Environment & Policies  
- **Temp files**: `./.tmp/` only (never `/tmp`, `~/`)
- **Config**: dynaconf, `VECTORDOTDEV_` env prefix
- **Python paths**: `PYTHONPATH=src` for vectordotdev testing
- **Component isolation**: Always `cd` to component directory first

## AI Assistant Tips

### For Cursor Users
- Use Cmd+K (Mac) / Ctrl+K (Windows/Linux) for inline edits
- Use @ symbols to reference files and symbols
- Composer mode for multi-file edits

### For Claude Code Users
- Use the integrated terminal for commands
- Multiple file edits in single response supported

### For ChatGPT/Claude.ai Users
- Copy-paste commands to your local terminal
- Request full file contents when needed
- Use step-by-step instructions for complex tasks

### Universal Best Practices
1. Always check TODO.md first for current tasks
2. Update TODO.md after completing tasks
3. Follow the 4-component architecture strictly
4. Test changes with real Vector subprocess validation
5. Use absolute paths when switching directories
