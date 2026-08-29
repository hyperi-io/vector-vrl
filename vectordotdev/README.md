# vectordotdev

The Python package that ships to PyPI. Runs VRL (Vector Remap Language)
in-process by wrapping the `vector-bindings` Rust crate - no `vector`
subprocess involved.

```bash
pip install vectordotdev
```

```python
from vectordotdev import execute_vrl, validate_vrl

execute_vrl('.level = upcase!(.level)', ['{"level": "info"}'])
# [{'level': 'INFO'}]

validate_vrl('.level = upcase!(.level)').success
# True
```

There is also a `Vector` class for running one VRL program over a batch.
Its `config` argument is accepted and stored but never applied - it is not a
config-driven pipeline. Full signatures, return shapes and the known gaps
are in
[docs/reference-python-api.md](../docs/reference-python-api.md).

## Build and test

Building this package compiles the Rust crate - `pyproject.toml` points
maturin at `../vector-bindings/Cargo.toml`, so a plain `pip install .` will
not do what you expect.

```bash
maturin develop --release     # local install, compiles the crate
maturin build --release       # wheel

PYTHONPATH=src uv run --with pytest --with pytest-asyncio pytest tests/
```

`tests/unit/test_vector_class.py` and `tests/unit/test_native_vrl_simple.py`
are the ground truth for what the bindings do. Tests needing the compiled
extension skip cleanly when it is absent.

Requires Python 3.12+.

## More

- [Root README](../README.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)
- [docs/how-to-build-and-test.md](../docs/how-to-build-and-test.md)
