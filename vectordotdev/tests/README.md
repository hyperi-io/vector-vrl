# vectordotdev Test Suite

Real pytest, organised by test type. No bespoke runner, no mocks - subprocess
tests get a real `vector` binary (locally built if found, else a throwaway
`timberio/vector` container, else skip/fail per `conftest.py`), and binding
tests use the compiled PyO3 module in-process.

## Overview

The test suite validates vectordotdev functionality including:
1. **Unit Tests**: Isolated component testing (VRL functions, subprocess Vector calls)
2. **Integration Tests**: Component interaction testing (vectordotdev Python bindings, subprocess Vector configs)
3. **E2E Tests**: End-to-end production scenarios (regex2vrl with real patterns)
4. **Smoke Tests**: Mandatory startup check (`smoke/test_startup.py`)

## Test Structure

```
vectordotdev/tests/
├── conftest.py                        # vector_runner fixture: run(args, cwd) against a real vector binary/container
├── smoke/                             # Mandatory startup smoke test
├── unit/                              # Unit tests - isolated components, no explicit marker
│   ├── test_native_vrl_*.py           # In-process PyO3 VRL execution (no subprocess)
│   ├── test_vrl_in_memory.py          # In-process VRL execution
│   └── test_*_vector*.py / test_*_subprocess.py  # Real vector subprocess tests (vector_runner fixture)
├── integration/                       # @pytest.mark.integration
│   ├── bindings.py                    # vectordotdev Python bindings, in-process, no subprocess
│   └── test_*.py                      # Bindings and subprocess-config integration tests
├── e2e/                                # @pytest.mark.e2e
│   ├── test_production_patterns.py    # Production pattern E2E tests
│   └── test_regex2vrl.py              # Full regex2vrl pipeline tests
├── manual/                            # NOT collected as tests - debug/audit/scratch scripts kept for reference
├── vrl/                                # Fixture data: sample logs and a VRL script
└── fixtures/                          # Shared test data and configurations
```

## Running Tests

```bash
# All tests
cd vectordotdev
uv run --with pytest pytest tests/ -v

# By marker
uv run --with pytest pytest tests/ -m unit -v
uv run --with pytest pytest tests/ -m integration -v
uv run --with pytest pytest tests/ -m e2e -v
uv run --with pytest pytest tests/ -m smoke -v

# A single file or test
uv run --with pytest pytest tests/unit/test_working_vector.py -v
```

`hyperi-ci run test -C vectordotdev` (what CI actually calls, via `make
test-python`) runs plain `pytest` under the hood - there is no separate
runner script to keep in sync.

### Vector binary resolution (see `conftest.py`)

The `vector_runner` fixture picks, in order: a locally-built binary
(`vector/target/release/vector` etc, or `vector` on `PATH`), then a one-shot
`docker run --rm timberio/vector:<pinned tag>` with the test's `tmp_path`
mounted as the working directory, then `pytest.skip` - or `pytest.fail` if
`$CI` is set, since a gate that cannot run must not silently pass. Expect
subprocess-backed unit/integration/e2e tests to skip in an environment with
neither a local vector checkout nor docker; that is correct behaviour, not a
bug.

## Test Categories

### Unit Tests (`unit/`)
Isolated component testing - no dependencies between tests. VRL function
tests run in-process against the compiled bindings; subprocess tests spin a
real `vector` process via `vector_runner` per test.

### Integration Tests (`integration/`)
Component interaction testing. `bindings.py` uses `vector.Vector()` directly,
in-process, no subprocess. Other files here exercise a real `vector`
subprocess against a generated config (regex2vrl output, YAML configs,
auto-stop behaviour, etc) via `vector_runner`.

### E2E Tests (`e2e/`)
Full regex2vrl -> VRL -> Vector -> validation pipelines against production-
shaped patterns (Apache/Nginx/syslog/JSON/Docker/Kubernetes logs, grok
patterns) via `vector_runner`.

## Manual / non-test scripts (`manual/`)

`tests/manual/` holds debug, audit, and scratch scripts that were previously
disguised as tests (`if __name__ == '__main__':`, print-based pass/fail, no
real assertions) - forcing pytest asserts onto them would have invented fake
coverage. They are not collected by pytest (no `test_*.py` naming, and
outside the collected tree in intent). Run one directly with `python
tests/manual/<script>.py` if you need the manual/human-in-the-loop check it
was written for. Some are candidates for outright deletion (fully superseded,
no remaining reference value) - flagged as such wherever that applies; ask
before removing.

## Known product bugs surfaced by this migration

Converting the bespoke subprocess/regex2vrl tests to real pytest asserts
surfaced genuine regex2vrl/grok conversion bugs that the old print-based
runner was silently swallowing. Tracked in GH issue #13 (with a follow-up
comment covering the wider grok/regex2vrl findings) - not re-litigated here.

## Adding New Tests

```python
# unit/ or integration/ - a real vector subprocess test
def test_new_pattern(vector_runner, tmp_path):
    config = tmp_path / "vector.yaml"
    config.write_text(render_config(some_vrl))
    result = vector_runner.run(["validate", str(config)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

# integration/ - mark it
import pytest

@pytest.mark.integration
def test_new_binding_case():
    ...

# e2e/ - mark it
@pytest.mark.e2e
def test_new_production_pattern(vector_runner, tmp_path):
    ...
```

## Troubleshooting

1. **Vector binary not found, no docker**: expected skip outside CI/a dev
   box with `vector` built - not a failure. Under `$CI` this is a hard
   `pytest.fail` instead, by design.
2. **vectordotdev import error** (bindings-based tests): the compiled PyO3
   module must be built and importable - see the top-level build docs.
3. **Slow/flaky subprocess tests**: mark genuinely slow ones
   `@pytest.mark.slow` so they can be excluded from a fast local loop
   (`-m "not slow"`).
