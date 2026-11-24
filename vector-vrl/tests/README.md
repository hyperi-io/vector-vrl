# vector-vrl test suite

Plain pytest, no bespoke runner and no mocks. Binding tests call the compiled PyO3 module in-process, and subprocess tests run a `vector` binary.

| Directory | What's in it |
|---|---|
| `smoke/` | `test_startup.py`: the package imports and `get_bindings_info()` reports a source |
| `unit/` | No marker. Most call the bindings in-process: `test_vector_class.py`, `test_native_vrl_simple.py`, enrichment tables, config checks, VRL's upstream examples, every stdlib function. `test_minimal_vector.py`, `test_quick_vector.py`, `test_simple_subprocess.py`, `test_working_ip_vrl.py` and `test_working_vector.py` run a `vector` binary through `vector_runner`. `test_readme_examples.py` runs every Python block in both READMEs except `>>>` transcripts |
| `integration/` | `@pytest.mark.integration`. `VectorTestRunner`, `validate_config_with_vector`, and in-process VRL against a `vector` subprocess on the same input |
| `e2e/` | `@pytest.mark.e2e`. A multi-branch VRL pipeline, run through the bindings and through `vector test` |
| `manual/` | Debug and audit scripts. Not collected: run one with `python tests/manual/<script>.py` |
| `data/` | The function expectation table and the dump of VRL's upstream examples |
| `vrl/`, `fixtures/` | Sample logs, VRL scripts, configs and patterns |

```bash
cd vector-vrl
uv run --with pytest pytest tests/ -v
uv run --with pytest pytest tests/ -m integration -v
uv run --with pytest pytest tests/ -m "not slow" -v
uv run --with pytest pytest tests/smoke -v
uv run --with pytest pytest tests/unit/test_working_vector.py -v
```

Unit tests have no marker, and the smoke test doesn't apply the declared `smoke` marker, so select those two by directory. `make test-python` at the root runs `hyperi-ci run test` here, which is plain pytest.

The `vector_runner` fixture in `conftest.py` takes the first of these: a local build (`vector/target/release/vector` and its siblings) or `vector` on `PATH`, then a one-shot `docker run --rm` of `timberio/vector` at the pinned `_VECTOR_TAG` and `_VECTOR_DIGEST` with the test's `tmp_path` mounted as the working directory. With neither it skips the test, or fails it when `$CI` is set, because a gate that can't run must not pass silently.

The integration tests take `vector_binary` from `integration/conftest.py` instead. It looks on `PATH` alone, with no container fallback, and skips or fails by the same rule. A new test follows one of these shapes:

```python
# unit/ or integration/ - a vector subprocess test
def test_new_pattern(vector_runner, tmp_path):
    config = tmp_path / "vector.yaml"
    config.write_text(render_config(some_vrl))
    result = vector_runner(["validate", str(config)], tmp_path)
    assert result.returncode == 0, result.stderr


# integration/ - mark it
import pytest


@pytest.mark.integration
def test_new_binding_case(): ...


# e2e/ - mark it
@pytest.mark.e2e
def test_new_production_pattern(vector_runner, tmp_path): ...
```

Mark a test over 30 seconds `@pytest.mark.slow`, so a fast local loop can leave it out with `-m "not slow"`. A bindings import error means the compiled module isn't built: see [docs/how-to-build-and-test.md](../../docs/how-to-build-and-test.md).
