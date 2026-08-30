# How to build and test

Three components, built separately. Run everything from inside the
component directory - the root is not a working directory for anything
except `make`.

## The whole repo at once

From the repo root:

```bash
make check      # quality + test, all three components
make quality    # lint/format only
make test       # tests only
make build      # builds the vector-vrl wheel
```

Each target wraps `hyperi-ci run <stage> -C <component>`. Narrower targets
exist when you only want one side: `quality-rust`, `quality-python`,
`test-rust`, `test-python`. Read the root `Makefile` - it is 31 lines and
tells you exactly what fans out where.

## Iterating on the Rust crate

```bash
cd vector-bindings
cargo build --release
cargo test              # the #[cfg(test)] module in src/lib.rs
```

`cargo test` covers the compiler and sandbox guards directly. It does NOT
rebuild the Python extension, which is the next section and the part people
lose an afternoon to.

## Getting your Rust change into Python

The compiled extension lives IN the source tree, at
`vector-vrl/src/vector-vrl/_bindings/vector_bindings.cpython-*.so`, and
it is gitignored. Nothing rebuilds it for you. Edit `lib.rs`, run your
Python tests, and they will happily exercise whatever `.so` was there
before - passing or failing for reasons that have nothing to do with your
change.

Rebuild it explicitly:

```bash
cd vector-bindings
maturin develop --release
```

If you suspect the `.so` is stale, compare timestamps:

```bash
ls -la vector-bindings/src/lib.rs
ls -la vector-vrl/src/vector-vrl/_bindings/*.so
```

An `.so` older than `lib.rs` is stale, and it fails silently - you get the
old behaviour with no warning at all. This is worth checking first whenever
a change you know you made appears to have no effect.

## Python 3.14 and the abi3 flag

pyo3 0.22 supports Python up to 3.13. On a machine whose default Python is
3.14 or newer, a raw `cargo build` needs:

```bash
env PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 cargo build --release
```

You only need this on 3.14+. Building through maturin from `vector-vrl/`
sets it for you - it is already in `vector-vrl/pyproject.toml` under
`[tool.maturin.environment]`.

## Testing the Python package

```bash
cd vector-vrl
PYTHONPATH=src uv run --with pytest --with pytest-asyncio --with pyyaml pytest tests/
```

The two files that describe the real, working API surface are
`tests/unit/test_vector_class.py` and `tests/unit/test_native_vrl_simple.py`
- 34 tests, and they run in about a tenth of a second because there is no
subprocess anywhere in them. If you want to know what the bindings actually
do rather than what a doc claims, read those two files.

Tests needing the compiled extension skip cleanly when it is absent
(`pytest.importorskip`), so a missing `.so` costs you those tests, not the
run.

Markers are declared in `pyproject.toml`: `integration`, `e2e`, `slow`,
`smoke`. Deselect the slow ones with `-m "not slow"`.

## `vector-bindings` needs no `vector/` checkout

The `vrl` crate comes straight from git in `vector-bindings/Cargo.toml`, so
`execute_vrl`, `validate_vrl`, `get_vrl_performance` and `Vector` all build
and run with nothing else cloned. `vector-bindings` reads no local Vector
source at all - see [architecture.md](architecture.md).

A `vector/` checkout is still used elsewhere in this repo: `build/`'s own
orchestrator compiles actual Vector from source as a build stage. See
[how-to-run-the-build-orchestrator.md](how-to-run-the-build-orchestrator.md).

## Building the wheel

```bash
cd vector-vrl
maturin build --release
```

This compiles the Rust crate as a side effect - `pyproject.toml` sets
`manifest-path = "../vector-bindings/Cargo.toml"`. A plain
`pip install .` does not do what a setuptools-shaped mental model expects
here, so use maturin.
