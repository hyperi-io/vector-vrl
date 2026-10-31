# vector-vrl

[![PyPI](https://img.shields.io/pypi/v/vector-vrl?logo=pypi)](https://pypi.org/project/vector-vrl/)
[![Python](https://img.shields.io/badge/python-3.14%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

Vector's own VRL compiler and runtime, compiled into a Python extension. Compile, check and run VRL, the language [Vector](https://vector.dev/) transforms events with, in your Python process, with no Vector binary to install and nothing to shell out to.

## What it gives you

- `validate_vrl`, which compiles without running, so a broken transform fails your test suite instead of your pipeline.
- `execute_vrl`, which runs a program over a batch of events on the same VRL runtime Vector uses. Nested objects come back as JSON strings, as [the API reference](docs/reference-python-api.md) sets out.
- `validate_config`, which compiles the inline VRL of each `remap` transform in a Vector config, in-process, and lists the `file:` ones it skipped and any it could not judge.
- `validate_config_with_vector`, the full check through a one-shot `vector validate`, where Vector is installed.
- No host or network functions in the published wheel, and a nesting limit that stops a crafted program overflowing the parser's stack.
- The real compiler to build playgrounds, linters, editor plugins and agent loops against.

## Quick start

```bash
pip install vector-vrl
```

```python
from vector_vrl import execute_vrl, validate_vrl

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

## Safer to hand untrusted VRL

Two guards apply to every entry point that compiles VRL:

- **No host, no network.** `get_env_var`, `get_hostname`, `http_request`,
  `dns_lookup` and six more are not compiled in. Caller-supplied VRL cannot
  read your environment or reach out of the process - it fails to compile
  instead. This is what the published wheel ships. Someone building the
  crate from source can turn those ten functions on with the `full-stdlib`
  Cargo feature; only do that where you control the VRL text.
- **No nesting bomb.** VRL source may not nest brackets past 64 levels. Past
  a few hundred the parser's own recursion overflows the stack and kills the
  process, which no Python `except` can catch, so the check runs before the
  parser ever sees the input. There is no way to switch this one off.

VRL also runs on a thread with 256 MiB of stack, so a long chain of operators
with no brackets compiles where the caller's thread would overflow.

Neither guard bounds memory. A short program that doubles a string in a loop
asks for gigabytes and aborts the process, and an operator chain tens of
thousands of terms long still overflows the VRL stack. So where the VRL comes
from someone who may be hostile - a multi-tenant playground, a
customer-supplied transform - run it in a child process under a memory limit
(`RLIMIT_AS`) and a time limit, and treat a dead child as a refused program.
The reasoning is in [docs/architecture.md](docs/architecture.md).

## The API

| | |
|---|---|
| `execute_vrl(vrl, events, secrets=None)` | Compile once, run over a batch, get the transformed events back |
| `execute_vrl_with_secrets(vrl, events, secrets=None)` | The same run, but each entry carries the event's secret store as well |
| `validate_vrl(vrl)` | Compile without running. Returns a `VrlResult`, never raises on bad VRL |
| `get_vrl_performance(vrl, events, iterations=100)` | Run it repeatedly, get events/sec |
| `Vector` | Batch runner holding state across calls - `.initialize()`, `.process_logs()`, `.get_stats()` |
| `validate_config(path\|dict)` | Compile every `remap` transform's VRL in a Vector config (YAML/TOML/JSON), in-process |
| `validate_config_with_vector(path)` | Full config check by running `vector validate` - needs the binary, never a daemon |

`Vector` runs the VRL step alone. Its `config` argument is stored but never
applied - there is no sources/transforms/sinks pipeline here. If you want the
full pipeline, run Vector itself.

### Checking a Vector config

There are two levels, and the difference matters.

`validate_config` is in-process and needs no `vector` binary. It compiles the
`source` of every `remap` transform and reports each by name. It says nothing
about sources, sinks or wiring, and it cannot judge VRL that calls
`get_enrichment_table_record` or `get_secret` - those are registered by Vector
from `enrichment_tables:` and secret backends declared in the config, outside
VRL, so this build has never heard of them. Rather than call a valid config
broken, it reports those transforms as `unchecked` with a reason.

`validate_config_with_vector` runs `vector validate --no-environment` and
checks the lot - wiring, component options, and the enrichment-backed VRL the
in-process check has to skip. It needs Vector installed, and it is one-shot:
Vector exits as soon as it has answered, never running as a daemon and never
moving data.

Exact signatures, return shapes, and the rough edges worth knowing (nested
objects come back as JSON strings, a per-event runtime error replaces that
event's dict) are in
[docs/reference-python-api.md](docs/reference-python-api.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache License, Version 2.0. See [LICENSE](LICENSE).

## Context

### What this is

One PyPI wheel out of a three-component checkout. Repo name and package name
match, which misleads: `vector-vrl/` is one directory of three, and the Rust
crate beside it does the compiling. VRL the language only -- no
sources/transforms/sinks pipeline, and `Vector`'s `config` argument is stored,
never applied. Nor is it a wrapper around a Vector checkout. `vector-bindings`
pulls the `vrl` crate from git and reads no local Vector source.

### Where things live

| Path | What it holds |
|---|---|
| `vector-bindings/` | Rust crate (PyO3). Compiles and runs VRL, sandbox guards and their tests in `src/lib.rs` |
| `vector-vrl/` | The package that ships to PyPI. maturin, not setuptools |
| `build/` | Orchestration CLI run in place as `./build/build`. Drives the other two, never imported by them |
| `Makefile` | The only thing the root is a working directory for |
| `docs/` | `architecture.md`, `how-to-build-and-test.md`, `reference-python-api.md` |

No manifest at the root, only the three below it
([issue #22](https://github.com/hyperi-io/vector-vrl/issues/22)).

### Commands that prove a change

```bash
make check      # quality + test, all three components
make quality    # lint and format only
make test       # tests only
make build      # the vector-vrl wheel
```

Also `quality-rust`, `quality-python`, `test-rust`, `test-python`. Each wraps
`uv run --directory <component> --with hyperi-ci hyperi-ci run <stage> -C .`,
since hyperi-ci has no multi-component repo model.

Green lies three ways, all silent:

- the gitignored `.so` under `vector-vrl/src/vector_vrl/_bindings/` is never
  rebuilt for you, and tests needing it `importorskip` out of the run
- tests that shell out to `vector` fall back binary -> docker -> skip. CI
  installs the version pinned in `vector-vrl/tests/conftest.py`
- the wheel smoke check skips the cross-built macOS x86_64 leg

Detail: [docs/how-to-build-and-test.md](docs/how-to-build-and-test.md).

### What tends to bite

| Don't | Do | Why |
|---|---|---|
| Edit `lib.rs`, then run the Python tests | `maturin develop --release` in `vector-bindings/` first | The tree's `.so` is stale and fails silently. Old behaviour, no warning |
| `pip install .` in `vector-vrl/` | `maturin build --release` | `manifest-path` points at `../vector-bindings/Cargo.toml`, so installing compiles the crate |
| A bare `uvx hyperi-ci` at the root | The `make` targets | It resolves pytest against PATH, not the component's venv. Dies on `unrecognized arguments: --cov=...`, or measures 0% from the wrong directory |
| A Python fenced block in either README as illustration | Real, runnable code | `test_readme_examples.py` executes every Python block in both. A rename once shipped `from vector-vrl import ...`. Ruff formatted it happily and the gate stayed green |
| Trust the `# vX.Y.Z` comment on a pinned action SHA | `gh api repos/<owner>/<repo>/commits/<sha>` | `ci.yml`'s `actions/download-artifact` pin is commented `# v7.0.0` and is really v4.3.0 |

### Where this sits

Inbound: **hyperi-io/scalo-py**, because `build/pyproject.toml` declares
`scalo[http]` by range. That is the orchestration CLI's dependency alone --
the published wheel has no runtime dependencies. The range has no upper bound,
so a scalo major lands here unopposed.

Outbound: nothing in the suite graph consumes this repo. Changes reach
consumers through PyPI.

The two upstreams that matter most are not suite members.
`vector-bindings/Cargo.toml` tracks **vectordotdev/vrl** at branch `main`, and
the test binary is a **vectordotdev/vector** release tarball.

## Issues

Open bugs: [this repo](https://github.com/hyperi-io/vector-vrl/issues?q=is%3Aopen+is%3Aissue+type%3ABug+-label%3Abacklog+-label%3Anext-minor) | [whole DFE suite](https://github.com/search?type=issues&q=is%3Aopen+is%3Aissue+type%3ABug+-label%3Abacklog+-label%3Anext-minor+repo%3Ahyperi-io%2Fdfe-infra+repo%3Ahyperi-io%2Fdfe-docker+repo%3Ahyperi-io%2Fdfe-deploy+repo%3Ahyperi-io%2Fdfe-engine+repo%3Ahyperi-io%2Fdfe-loader+repo%3Ahyperi-io%2Fdfe-receiver+repo%3Ahyperi-io%2Fdfe-fetcher+repo%3Ahyperi-io%2Fdfe-archiver+repo%3Ahyperi-io%2Fdfe-transform-vrl+repo%3Ahyperi-io%2Fdfe-transform-vector+repo%3Ahyperi-io%2Fdfe-transform-elastic+repo%3Ahyperi-io%2Fdfe-ui+repo%3Ahyperi-io%2Fdfe-hyperdx+repo%3Ahyperi-io%2Fscalo-rs+repo%3Ahyperi-io%2Fscalo-py+repo%3Ahyperi-io%2Flogreducer+repo%3Ahyperi-io%2Fdfe-schemas+repo%3Ahyperi-io%2Fvector-vrl+repo%3Ahyperi-io%2Fculvert+repo%3Ahyperi-io%2Fdfe-clickhouse-rs+repo%3Ahyperi-io%2Ffactbook-rs)
