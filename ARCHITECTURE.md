# Architecture

Three independent components in one checkout. No single venv, lockfile, or
`pip install -e .` covers the whole tree - each one gets built and tested
from inside its own directory.

## The three components

| Component | Language | Build | What it does |
|---|---|---|---|
| `vector-bindings/` | Rust (Cargo, PyO3) | `cargo` / `maturin` | Compiles and runs VRL via the real `vrl` compiler, exposes the result to Python |
| `vectordotdev/` | Python | maturin (not pip/setuptools) | The package that ships to PyPI - wraps `vector-bindings` |
| `build/` | Python | `uv`, its own `pyproject.toml` | A separate orchestration CLI. Not a dependency of the other two - it drives them, it isn't driven by them |

Dependency direction is one-way: `vector-bindings` -> `vectordotdev`,
orchestrated (not depended on) by `build/`.

`vectordotdev/pyproject.toml` builds via maturin, with `manifest-path`
pointing at `../vector-bindings/Cargo.toml` - installing the Python package
always compiles the Rust crate. A plain `pip install .` from a
setuptools-shaped mental model will not do what you expect here.

## The missing fourth piece: `vector/`

`vector-bindings/build.rs` walks `../vector/lib/vector-core/src/event` and
`../vector/lib/vector-common/src` (upstream [vectordotdev/vector](https://github.com/vectordotdev/vector)
source) to auto-discover Vector's public structs and enums, and generates
one placeholder Python class per type it finds.

This path:

- is gitignored (`/vector/`) - it's never committed to this repo
- is NOT present in a fresh checkout - clone it yourself, as a sibling of
  `vector-bindings/`
- degrades SILENTLY, not loudly. Missing, `build.rs` prints a
  `cargo:warning=... not found, skipping` and carries on, producing zero
  auto-discovered classes instead of failing the build

A build that "succeeds" with `vector/` absent gives you a working crate
with far fewer exposed classes than you'd get otherwise. Check the build
output for that warning before trusting anything about API coverage - and
know that even fully populated, those auto-generated classes are
placeholders, not real bindings to the underlying Rust types (tracked in
[issue #15](https://github.com/hyperi-io/vectordotdev/issues/15)).

The VRL compiler itself is a separate story: `vrl` is pulled straight from
`https://github.com/vectordotdev/vrl.git` (branch `main`) in
`vector-bindings/Cargo.toml`. That dependency does NOT come from the local
`vector/` checkout, so VRL execution (`execute_vrl`, `validate_vrl`,
`Vector`) works fine with `vector/` absent. Only the auto-discovered
placeholder classes need it.

## Component boundaries

- Never edit anything under `vector/` - it's upstream, read-only, and not
  tracked here anyway.
- `vectordotdev/src/vectordotdev/_bindings/` is the only piece that needs
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
