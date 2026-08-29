# vector-bindings

The Rust crate. Compiles and runs VRL using the real `vrl` compiler and
exposes the result to Python through PyO3.

Internal to this repo - it does not publish standalone. The artefact that
ships is `../vectordotdev`, which wraps this crate via maturin.

## Build and test

```bash
cargo build --release
cargo test                  # unit tests in src/lib.rs
maturin develop --release   # rebuild the .so the Python package imports
```

`cargo test` does NOT rebuild the Python extension. If you changed `lib.rs`
and Python still shows the old behaviour, you skipped `maturin develop` -
the `.so` lives in `../vectordotdev/src/vectordotdev/_bindings/` and goes
stale silently.

On Python 3.14+, a raw `cargo build` needs
`PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` (pyo3 0.22 supports up to 3.13).
Building through maturin sets it for you.

## What is in here

`src/lib.rs` is the whole hand-written API: `execute_vrl`, `validate_vrl`,
`get_vrl_performance`, `Vector` and `VrlResult`, plus the two guards that
keep caller-supplied VRL from reading the host environment or overflowing
the parser stack.

`build.rs` generates a placeholder Python class per public type it finds in
a sibling `../vector/` checkout. Those are not real bindings - see
[docs/explanation-auto-discovery.md](../docs/explanation-auto-discovery.md).

The `vrl` dependency is pinned to a deliberately narrow feature set. Read
"VRL execution's security posture" in
[ARCHITECTURE.md](../ARCHITECTURE.md) before you widen it.

## More

- [Root README](../README.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)
- [docs/how-to-build-and-test.md](../docs/how-to-build-and-test.md)
- [docs/reference-python-api.md](../docs/reference-python-api.md)
