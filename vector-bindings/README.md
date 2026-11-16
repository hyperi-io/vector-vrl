# vector-bindings

The Rust crate. Compiles and runs VRL with the `vrl` compiler and hands the result to Python through PyO3. It doesn't publish standalone: the artefact that ships is `../vector-vrl`, which wraps this crate through maturin.

`src/lib.rs` is the hand-written API: `execute_vrl`, `execute_vrl_with_secrets`, `validate_vrl`, `get_vrl_performance`, the enrichment-table registry functions, `Vector` and `VrlResult`. `src/enrichment.rs` and `src/secrets.rs` add the VRL functions the standalone `vrl` crate doesn't ship: the two enrichment-table lookups, and `get_secret`/`set_secret`/`remove_secret` over the event's secret store. `src/nesting.rs` is the bracket-depth guard that runs before the parser.

```bash
cargo build --release
cargo test                  # the test modules in src/
maturin develop --release   # rebuild the .so the Python package imports
```

`cargo test` does NOT rebuild the Python extension. If you changed `lib.rs` and Python shows the old behaviour, you skipped `maturin develop`: the `.so` lives in `../vector-vrl/src/vector_vrl/_bindings/` and goes stale silently.

The crate builds against CPython's stable ABI (`pyo3/abi3-py312`), so one wheel per platform serves every Python release the package supports. It reads no local Vector checkout either. The `vrl` dependency comes straight from git and is all VRL execution needs.

`vrl` is pinned to a narrow feature set. The crate's `full-stdlib` feature widens it to vrl's complete stdlib, adding ten functions that read the host environment, resolve DNS and make outbound HTTP requests. It's off by default and the published wheel is built without it. Read [What caller-supplied VRL cannot reach](../docs/architecture.md#what-caller-supplied-vrl-cannot-reach) before you turn it on.

```bash
cargo build --release                        # sandboxed, the default
cargo build --release --features full-stdlib # trusted VRL only
```

More: the [root README](../README.md), [architecture](../docs/architecture.md), [how to build and test](../docs/how-to-build-and-test.md) and the [Python API reference](../docs/reference-python-api.md).
