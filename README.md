# vector-vrl

**Run Vector's transform language in Python. In-process, no subprocess.**

[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)

VRL - the [Vector Remap Language](https://vector.dev/docs/reference/vrl/) - is
the thing that makes [Vector](https://vector.dev/) good at logs. Parse, filter,
redact, reshape, enrich, all in a language built for exactly that and nothing
else. The catch has always been that it only runs inside the `vector` binary.

This package compiles Vector's actual VRL compiler and runtime into a Python
extension. Not a subprocess wrapper, not a reimplementation that is subtly
wrong at the edges - the same engine, in your process.

```bash
pip install vector-vrl
```

```python
from vector-vrl import execute_vrl, validate_vrl

vrl = """
parsed, err = parse_json(.message)
if err == null {
    .level = parsed.level
}
"""

execute_vrl(vrl, ['{"message": "{\\"level\\": \\"info\\"}"}'])
# [{'level': 'info', 'message': '{"level": "info"}'}]

validate_vrl(vrl).success
# True
```

## What it is good for

- **Test VRL in CI** without installing Vector. `validate_vrl` compiles
  without running, so a broken transform fails your test suite instead of
  your pipeline.
- **Check a Vector config before you ship it.** `validate_config` walks a
  YAML/TOML/JSON config and compiles every `remap` transform's VRL, catching
  the most common way a config breaks. It checks the VRL, not the sinks -
  see the caveat under The API.
- **Build VRL tooling** - playgrounds, linters, editor plugins, config
  generators - against the real compiler rather than a regex approximation.
- **Process events in Python** with semantics identical to what your Vector
  deployment will do to the same data.
- **Benchmark a transform** before it goes anywhere near production.
- **AI agents** for vrl processing and development loops

## Safer to hand untrusted VRL

Two guards apply to every entry point that compiles VRL, unconditionally and
with no way to switch them off:

- **No host, no network.** `get_env_var`, `get_hostname`, `http_request` and
  `dns_lookup` are not compiled in. Caller-supplied VRL cannot read your
  environment or reach out of the process - it fails to compile instead.
- **No nesting bomb.** VRL source may not nest brackets past 64 levels. Past
  a few hundred the parser's own recursion overflows the stack and kills the
  process, which no Python `except` can catch, so the check runs before the
  parser ever sees the input.

That combination is what makes it reasonable to accept VRL from a user - a
multi-tenant playground, a customer-supplied transform, a config someone
pasted in. The reasoning is in
[docs/architecture.md](docs/architecture.md).

## The API

| | |
|---|---|
| `execute_vrl(vrl, events)` | Compile once, run over a batch, get the transformed events back |
| `validate_vrl(vrl)` | Compile without running. Returns a `VrlResult`, never raises on bad VRL |
| `get_vrl_performance(vrl, events, iterations=100)` | Run it repeatedly, get events/sec |
| `Vector` | Batch runner holding state across calls - `.initialize()`, `.process_logs()`, `.get_stats()` |
| `validate_config(path\|dict)` | Compile every `remap` transform's VRL in a Vector config (YAML/TOML/JSON) |

`Vector` runs the VRL step alone. Its `config` argument is stored but never
applied - there is no sources/transforms/sinks pipeline here. If you want the
full pipeline, run Vector itself.

`validate_config` is a VRL check, not a Vector config check. It compiles the
`source` of every `remap` transform and reports each one by name; a remap
reading its VRL from `file:` is listed as skipped rather than guessed at.
It says nothing about sources, sinks, wiring or type compatibility - for
that, run `vector validate`.

Exact signatures, return shapes, and the rough edges worth knowing (nested
objects come back as JSON strings, a per-event runtime error replaces that
event's dict) are in
[docs/reference-python-api.md](docs/reference-python-api.md).

## The repo

Three components sharing one checkout. This is not a normal Python repo and
`pip install -e .` will not do what you expect:

- **`vector-bindings/`** - the Rust crate. Compiles VRL, runs it, hands the
  result to Python via [PyO3](https://pyo3.rs/).
- **`vector-vrl/`** - the package that ships to PyPI. Wraps the crate via
  [maturin](https://github.com/PyO3/maturin), so building it compiles Rust.
- **`build/`** - a separate orchestration CLI. Not a dependency of either.

[docs/architecture.md](docs/architecture.md) has the layout and the dependency
direction. [docs/how-to-build-and-test.md](docs/how-to-build-and-test.md) is
how to build it from source (needs the Rust toolchain).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache License, Version 2.0. See [LICENSE](LICENSE).
