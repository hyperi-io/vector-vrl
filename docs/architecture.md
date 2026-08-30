# Architecture

Three independent components in one checkout. No single venv, lockfile, or
`pip install -e .` covers the whole tree - each one gets built and tested
from inside its own directory.

## The three components

| Component | Language | Build | What it does |
|---|---|---|---|
| `vector-bindings/` | Rust (Cargo, PyO3) | `cargo` / `maturin` | Compiles and runs VRL via the real `vrl` compiler, exposes the result to Python |
| `vector-vrl/` | Python | maturin (not pip/setuptools) | The package that ships to PyPI - wraps `vector-bindings` |
| `build/` | Python | `uv`, its own `pyproject.toml` | A separate orchestration CLI. Not a dependency of the other two - it drives them, it isn't driven by them |

Dependency direction is one-way: `vector-bindings` -> `vector-vrl`,
orchestrated (not depended on) by `build/`.

`vector-vrl/pyproject.toml` builds via maturin, with `manifest-path`
pointing at `../vector-bindings/Cargo.toml` - installing the Python package
always compiles the Rust crate. A plain `pip install .` from a
setuptools-shaped mental model will not do what you expect here.

## `vector-bindings` is self-contained

`vector-bindings` reads no local Vector checkout at all. The VRL compiler
(`vrl` crate) is pulled straight from `https://github.com/vectordotdev/vrl.git`
(branch `main`) in `vector-bindings/Cargo.toml`, so `execute_vrl`,
`validate_vrl`, `get_vrl_performance` and `Vector` are fully functional from
a fresh checkout with nothing else cloned.

An earlier `build.rs` step walked a sibling `vector/` checkout to
auto-generate one placeholder Python class per public Vector struct/enum it
found - no real binding behind any of them. That mechanism has been removed
entirely, not fixed (it was [issue #15](https://github.com/hyperi-io/vector-vrl/issues/15)).

A `vector/` checkout still exists as a concept in this repo: `build/`'s own
orchestrator compiles actual Vector from source as one of its build stages
(see [how-to-run-the-build-orchestrator.md](how-to-run-the-build-orchestrator.md)).
That is unrelated to `vector-bindings` or `vector-vrl` - neither reads it.

## Component boundaries

- Never edit anything under `vector/` - it's upstream, read-only, and not
  tracked here anyway.
- `vector-vrl/src/vector-vrl/_bindings/` is the only piece that needs
  the compiled `vector_bindings` `.so` - this is the one part of the
  Python package that requires the full Rust build chain.
- `build/` orchestrates builds across the other two components; it is
  never imported by them.

## VRL execution's security posture

`vector-bindings` deliberately restricts the `vrl` crate's feature set:
`stdlib-base` + `enable_crypto_functions` only, `default-features = false`.
The crate's own default feature set also turns on functions that read the
host environment and make outbound network requests (`get_env_var`,
`http_request`, `dns_lookup`, `get_hostname`) - since this crate compiles
and runs whatever VRL text a Python caller hands it, those stay off. If you
add a dependency on a broader `vrl` feature set, check what it re-enables
before you ship it.

A VRL source string also can't nest more than 64 levels deep
(`MAX_VRL_NESTING_DEPTH` in `lib.rs`) - past a few hundred levels the
parser's own recursion overflows the stack and crashes the process. Both
of these are covered by regression tests in `vector-bindings/src/lib.rs`'s
`#[cfg(test)]` module.
