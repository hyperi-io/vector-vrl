# vectordotdev

Python bindings for [Vector](https://vector.dev/), the observability data
pipeline. Run VRL (Vector Remap Language) against events without shelling
out to the `vector` binary - the compiler and runtime are compiled straight
into the Python extension via [PyO3](https://pyo3.rs/).

[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

## What actually works right now

VRL execution, in-process. That's it, and it's real - not a wrapper around
a subprocess, not a mock:

```python
from vectordotdev._bindings import execute_vrl, validate_vrl

vrl = """
parsed, err = parse_json(.message)
if err == null {
    .level = parsed.level
}
"""

events = ['{"message": "{\\"level\\": \\"info\\"}"}']
result = execute_vrl(vrl, events)
print(result)  # [{'level': 'info', 'message': '...'}]

check = validate_vrl(vrl)
print(check.success)  # True
```

`validate_vrl` compiles without running - use it to lint VRL before you ship
it. `get_vrl_performance(vrl, events, iterations=100)` runs the same VRL
repeatedly and reports events/sec.

There's also a `Vector` class (`Vector(config)`, `.initialize()`,
`.process_logs(logs, vrl_code)`, `.get_stats()`) for running the same VRL
against a batch without touching `_bindings` directly. Be aware: the
`config` dict it takes is parsed and stored but not yet wired into
`process_logs` - construct it with whatever you like, it won't change what
runs. Full sources/transforms/sinks pipeline configuration (the way you'd
configure the real `vector` binary) is NOT implemented. If that's what
you're after, use `execute_vrl` directly and drive your own event loop
around it.

## What's tracked as broken, not shipped

- `regex2vrl` (a regex-to-VRL pattern converter) - removed from the public
  API, source archived locally, see [issue #13](https://github.com/hyperi-io/vectordotdev/issues/13).
- The auto-exposed "96 Vector APIs" `build.rs` generates from the upstream
  Vector source are placeholder classes, not real bindings to those types -
  see [issue #15](https://github.com/hyperi-io/vectordotdev/issues/15).

Neither of these will surprise you if you stick to `execute_vrl`/
`validate_vrl`/`get_vrl_performance` and the `Vector` class as described
above - that surface is the one with real tests behind it.

## Install

```bash
pip install vectordotdev
```

Building from source needs the Rust toolchain (the package wraps a
compiled crate, `vector-bindings/` - see that component's own README) and
[maturin](https://github.com/PyO3/maturin). See
[docs/how-to-build-and-test.md](docs/how-to-build-and-test.md).

## The repo

Three independent components sharing this checkout - not one project, and
"install and pip install -e ." will not work as you'd expect from a normal
Python repo:

- `vector-bindings/` - the Rust crate. Compiles VRL, runs it, exposes the
  result to Python.
- `vectordotdev/` - the package that actually ships to PyPI. Wraps
  `vector-bindings` via maturin.
- `build/` - a separate orchestration CLI, not a dependency of the other
  two.

[ARCHITECTURE.md](ARCHITECTURE.md) has the full layout, the dependency
direction, and the one genuine gotcha (an upstream Vector checkout that's
required for full API auto-discovery and silently degrades to nothing if
you forget to clone it).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache License, Version 2.0. See [LICENSE](LICENSE).

## Related projects

- [Vector](https://vector.dev/) - the data processing engine this wraps
- [VRL](https://vector.dev/docs/reference/vrl/) - the transform language
- [PyO3](https://pyo3.rs/) - Python bindings for Rust
- [maturin](https://github.com/PyO3/maturin) - builds this package
