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
make build      # builds the vectordotdev wheel
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
`vectordotdev/src/vectordotdev/_bindings/vector_bindings.cpython-*.so`, and
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
ls -la vectordotdev/src/vectordotdev/_bindings/*.so
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

You only need this on 3.14+. Building through maturin from `vectordotdev/`
sets it for you - it is already in `vectordotdev/pyproject.toml` under
`[tool.maturin.environment]`.

## Testing the Python package

```bash
cd vectordotdev
PYTHONPATH=src uv run --with pytest --with pytest-asyncio pytest tests/
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

## The `vector/` checkout

`vector-bindings/build.rs` walks a sibling `vector/` directory - an upstream
[vectordotdev/vector](https://github.com/vectordotdev/vector) clone - to
auto-discover public types. It is gitignored and absent from a fresh
checkout, so clone it yourself next to `vector-bindings/`:

```bash
git clone https://github.com/vectordotdev/vector.git
```

Missing, the build still SUCCEEDS. `build.rs` prints
`cargo:warning=... not found, skipping` and generates zero classes from that
path. Check the build output before trusting any statement about API
coverage:

```
warning: ...   ../vector/lib/vector-core/src/event - 46 APIs
warning: ...   ../vector/lib/vector-common/src - 50 APIs
warning: ... Discovered 96 unique Vector APIs across all modules
```

Those counts are what the build script printed on this repo at the time of
writing. Trust the number your own build prints, not this one - and see
[explanation-auto-discovery.md](explanation-auto-discovery.md) for what
those classes are and are not.

VRL execution does not need `vector/` at all. The `vrl` crate comes straight
from git in `vector-bindings/Cargo.toml`, so `execute_vrl`, `validate_vrl`,
`get_vrl_performance` and `Vector` all work with `vector/` absent. Only the
auto-discovered classes need it. The full picture is in
[ARCHITECTURE.md](../ARCHITECTURE.md).

## Building the wheel

```bash
cd vectordotdev
maturin build --release
```

This compiles the Rust crate as a side effect - `pyproject.toml` sets
`manifest-path = "../vector-bindings/Cargo.toml"`. A plain
`pip install .` does not do what a setuptools-shaped mental model expects
here, so use maturin.
