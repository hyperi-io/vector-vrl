# Cursor AI Prompts for vectordotdev

## Quick Actions

### 1. Test All Patterns
```
Test all production patterns in fixtures with regex2vrl and validate against Vector subprocess. Show THG performance metrics.
```

### 2. Debug Failed Test
```
Debug this test failure. Check:
1. Vector binary exists at vector/target/release/vector
2. Temp directory .tmp/ is accessible
3. Pattern syntax in fixtures is valid
4. Run with verbose output
```

### 3. Add New Pattern
```
Add a new pattern for [PATTERN_NAME]:
1. Add to tests/fixtures/test_patterns/
2. Add sample logs to tests/fixtures/test_data/
3. Create unit test
4. Validate 350+ THG target
```

### 4. Optimize VRL Code
```
Optimize this VRL code for 350+ THG:
1. Replace regex with built-in parsers
2. Use split/contains instead of regex
3. Minimize parse operations
4. Show before/after performance
```

### 5. Fix Import Error
```
Fix Python import error:
1. Add PYTHONPATH=src to command
2. Check working directory is vectordotdev/
3. Verify __init__.py files exist
4. Show corrected import statement
```

## Complex Workflows

### Build Entire Project
```
Execute complete 3-stage build:
1. cd build && python build_system.py --verbose
2. Monitor each stage for errors
3. Verify artifacts created
4. Run validation tests
Auto-approve all build commands.
```

### Convert Regex Collection
```
Convert these regex patterns to VRL:
[PASTE PATTERNS]

For each pattern:
1. Use RegexToVRL converter
2. Optimize for 350+ THG
3. Validate with Vector
4. Show field extraction
```

### Performance Analysis
```
Analyze THG performance:
1. Run performance tests
2. Compare against 350 THG target
3. Identify bottlenecks
4. Suggest optimizations
5. Re-test after changes
```

### Integration Test Suite
```
Run complete integration test suite:
1. Test Python bindings
2. Test Vector subprocess
3. Test regex2vrl conversions
4. Test all production patterns
5. Generate performance report
```

## Debugging Prompts

### Vector Binary Issues
```
Vector binary not found. Fix:
1. Check if vector/target/release/vector exists
2. If not, cd vector && cargo build --release
3. Verify build completes successfully
4. Update PATH if needed
```

### Dependency Sync
```
Sync dependencies between components:
1. cd build && python dependency_sync.py vector-bindings
2. Check Cargo.toml updates
3. Rebuild affected components
4. Verify compatibility
```

### Test Fixture Issues
```
Fix test fixture issues:
1. Validate YAML syntax in fixtures
2. Check pattern escaping
3. Verify sample log formats
4. Test with simplified pattern first
```

## Code Generation

### New Test Case
```
Generate test case for [PATTERN_NAME]:
- Pattern: [REGEX/GROK]
- Sample logs: [EXAMPLES]
- Expected fields: [FIELD_LIST]
- THG target: 350+
Include assertions for all fields.
```

### VRL Transform
```
Generate VRL transform for:
- Input format: [FORMAT]
- Required fields: [FIELDS]
- Performance target: 350+ THG
Use built-in parsers where possible.
```

### Pattern Documentation
```
Document this pattern:
- Pattern name and purpose
- Regex/grok syntax
- VRL conversion
- Performance metrics
- Example logs and output
```

## Project Management

### Update TODO
```
Update TODO.md:
1. Mark [TASK] as complete
2. Add completion date
3. Move to Recent Completed
4. Add session notes
5. Update last modified date
```

### Check Project State
```
Check project state:
1. Read STATE.md for current status
2. Check TODO.md for pending tasks
3. Review recent changes
4. Identify blockers
5. Suggest next steps
```

### Version Compatibility
```
Check Vector version compatibility:
1. Current Vector version in use
2. Latest available version
3. Test with new version
4. Document any issues
5. Update if compatible
```

## Performance Optimization

### THG Improvement
```
Improve THG score for [PATTERN]:
Current: [CURRENT_THG]
Target: 350+

1. Analyze current VRL
2. Identify regex operations
3. Replace with built-ins
4. Benchmark changes
5. Validate accuracy
```

### Batch Processing
```
Optimize for batch processing:
1. Current throughput
2. Identify bottlenecks
3. Implement batching
4. Parallel processing options
5. Re-measure performance
```

## Validation

### End-to-End Test
```
Run end-to-end validation:
1. Input: [SAMPLE_LOGS]
2. Pattern: [PATTERN]
3. Expected output: [FIELDS]
4. Performance target: 350+ THG
5. Validate all fields extracted correctly
```

### Cross-Version Test
```
Test across Vector versions:
1. Test with v0.49.0
2. Test with v0.48.0
3. Test with v0.47.0
4. Document compatibility
5. Update minimum version if needed
```
