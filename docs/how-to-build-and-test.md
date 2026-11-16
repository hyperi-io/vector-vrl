# How to build and test

Three components, built separately. Run everything from inside the component directory: the root is a working directory for `make` and nothing else. From the root:

```bash
make check      # quality + test, all three components
make quality    # lint and format
make test       # tests
make build      # the vector-vrl wheel
```

Each target runs `uv run --directory <component> --with hyperi-ci hyperi-ci run <stage> -C .` for the components it covers. The narrower targets are `quality-rust`, `quality-python`, `test-rust` and `test-python`, and the root `Makefile` shows what fans out where.

## Getting a Rust change into Python

```bash
cd vector-bindings
cargo build --release
cargo test               # the test modules in src/
maturin develop --release
```

`cargo test` covers the compiler, the guards, enrichment tables and secrets in Rust. It doesn't rebuild the Python extension, and that's the step people miss.

The compiled extension sits in the source tree at `vector-vrl/src/vector_vrl/_bindings/vector_bindings.*.so`, gitignored. The first `uv run` in `vector-vrl/` builds it when it creates the venv, and a later Rust edit doesn't trigger a rebuild. Edit `lib.rs`, run the Python tests, and they exercise whatever `.so` was there before, passing or failing for reasons that have nothing to do with your change. `maturin develop --release` is what rebuilds it.

When a change you know you made seems to have no effect, compare timestamps first:

```bash
ls -la vector-bindings/src/lib.rs
ls -la vector-vrl/src/vector_vrl/_bindings/*.so
```

An `.so` older than `lib.rs` is stale, and it fails silently: the old behaviour, no warning.

## Testing and building the Python package

```bash
cd vector-vrl
PYTHONPATH=src uv run --with pytest --with pytest-asyncio --with pyyaml pytest tests/
```

`tests/unit/test_vector_class.py` and `tests/unit/test_native_vrl_simple.py` describe the working API surface, with no subprocess anywhere in them. To know what the bindings do rather than what a doc claims, read those two files. [vector-vrl/tests/README.md](../vector-vrl/tests/README.md) maps the rest of the suite.

Tests needing the compiled extension skip cleanly when it's absent (`pytest.importorskip`), so a missing `.so` costs you those tests, not the run. Markers are declared in `pyproject.toml`: `integration`, `e2e`, `slow`, `smoke`. Deselect the slow ones with `-m "not slow"`.

`vector-bindings` needs no Vector checkout to build or test ([architecture](architecture.md)). The [build orchestrator](how-to-run-the-build-orchestrator.md) is the one thing here that compiles Vector itself.

Build the wheel with maturin:

```bash
cd vector-vrl
maturin build --release
```

This compiles the Rust crate as a side effect, because `pyproject.toml` sets `manifest-path = "../vector-bindings/Cargo.toml"`. A plain `pip install .` doesn't do what a setuptools habit expects here, so use maturin.

`vector-bindings` sets `pyo3/abi3-py312`, so it compiles against CPython's stable ABI and the wheel is tagged `cp312-abi3`: one wheel per platform, not one per Python release. Which releases pip installs it on is set by `requires-python` in `vector-vrl/pyproject.toml`, not by the tag.
