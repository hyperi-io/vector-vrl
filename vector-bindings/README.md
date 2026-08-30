# vector-bindings

The Rust crate. Compiles and runs VRL using the real `vrl` compiler and
exposes the result to Python through PyO3.

Internal to this repo - it does not publish standalone. The artefact that
ships is `../vector-vrl`, which wraps this crate via maturin.

## Build and test

```bash
cargo build --release
cargo test                  # unit tests in src/lib.rs
maturin develop --release   # rebuild the .so the Python package imports
```

`cargo test` does NOT rebuild the Python extension. If you changed `lib.rs`
and Python still shows the old behaviour, you skipped `maturin develop` -
the `.so` lives in `../vector-vrl/src/vector-vrl/_bindings/` and goes
stale silently.

On Python 3.14+, a raw `cargo build` needs
`PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` (pyo3 0.22 supports up to 3.13).
Building through maturin sets it for you.

## What is in here

`src/lib.rs` is the whole hand-written API: `execute_vrl`,
`execute_vrl_with_secrets`, `validate_vrl`, `get_vrl_performance`, `Vector`
and `VrlResult`, plus the two guards that keep caller-supplied VRL from
reading the host environment or overflowing the parser stack.

`src/enrichment.rs` and `src/secrets.rs` add the VRL functions the standalone
`vrl` crate does not ship - the two enrichment-table lookups, and
`get_secret`/`set_secret`/`remove_secret` over the event's secret store.

This crate reads no local Vector checkout - the `vrl` dependency is pulled
straight from git and is the whole of what makes VRL execution work.

The `vrl` dependency is pinned to a deliberately narrow feature set. The
crate's `full-stdlib` feature widens it to vrl's complete stdlib, adding ten
functions that read the host environment, resolve DNS and make outbound HTTP
requests. It is off by default and the published wheel is built without it.
Read "VRL execution's security posture" in
[docs/architecture.md](../docs/architecture.md) before you turn it on.

```bash
cargo build --release                        # sandboxed, the default
cargo build --release --features full-stdlib # trusted VRL only
```

## More

- [Root README](../README.md)
- [docs/architecture.md](../docs/architecture.md)
- [docs/how-to-build-and-test.md](../docs/how-to-build-and-test.md)
- [docs/reference-python-api.md](../docs/reference-python-api.md)
