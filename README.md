# vector-vrl

Vector's own VRL compiler and runtime, in your Python process.

[![PyPI](https://img.shields.io/pypi/v/vector-vrl?logo=pypi)](https://pypi.org/project/vector-vrl/)
[![Python](https://img.shields.io/badge/python-3.14%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

Compile, check and run VRL, the language [Vector](https://vector.dev/) transforms events with, from Python. There's no Vector binary to install and nothing to shell out to: the compiler is a Python extension.

## What it gives you

- `validate_vrl`, which compiles without running, so a broken transform fails your test suite instead of your pipeline.
- `execute_vrl`, which runs a program over a batch of events on the same VRL runtime Vector uses. Nested objects come back as JSON strings, as [the API reference](docs/reference-python-api.md) sets out.
- `validate_config`, which compiles the inline VRL of each `remap` transform in a Vector config, in-process, and lists the `file:` ones it skipped and any it could not check.
- `validate_config_with_vector`, the full check through a one-shot `vector validate`, where Vector is installed.
- Enrichment tables and event secrets, the VRL functions Vector adds on top of the `vrl` crate.
- No host or network functions in the published wheel, and a nesting limit that stops a crafted program overflowing the parser's stack.

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

Two guards apply to every entry point that compiles VRL.

The environment, system and network functions aren't compiled in. `get_env_var`, `get_hostname`, `http_request`, `dns_lookup` and six more fail to compile, so caller-supplied VRL can't read your environment or reach out of the process. A source build can turn the ten back on with the `full-stdlib` Cargo feature. Turn them on just where you control the VRL text.

VRL source may not nest brackets past 64 levels, and nothing switches that check off. Deep enough nesting overflows the parser's recursion and kills the process, which no Python `except` can catch, so the check runs before the parser sees the input. VRL runs on a thread with 256 MiB of stack as well, so a long chain of operators with no brackets compiles where the caller's thread would overflow.

Neither guard bounds memory. A short program that doubles a string in a loop asks for gigabytes and aborts the process, and an operator chain tens of thousands of terms long still overflows the VRL stack. So where the VRL comes from someone who may be hostile (a multi-tenant playground, a customer-supplied transform), run it in a child process under a memory limit (`RLIMIT_AS`) and a time limit, and treat a dead child as a refused program. The reasoning is in [docs/architecture.md](docs/architecture.md#what-caller-supplied-vrl-cannot-reach).

## The API

| | |
|---|---|
| `execute_vrl(vrl, events, secrets=None)` | Compile once, run over a batch, get the transformed events back |
| `execute_vrl_with_secrets(vrl, events, secrets=None)` | The same run, but each entry holds the event's secret store as well |
| `validate_vrl(vrl)` | Compile without running. Returns a `VrlResult`, never raises on bad VRL |
| `get_vrl_performance(vrl, events, iterations=100)` | Run it repeatedly, get events/sec |
| `register_enrichment_table(name, kind, path)` | Load a CSV or GeoIP table for VRL's enrichment lookups. `list_enrichment_tables` and `clear_enrichment_tables` manage the registry |
| `Vector` | Batch runner holding stats across calls: `.initialize()`, `.process_logs()`, `.get_stats()` |
| `validate_config(path\|dict)` | Compile every `remap` transform's VRL in a Vector config (YAML/TOML/JSON), in-process |
| `validate_config_with_vector(path)` | Full config check by running `vector validate`. Needs the binary, never a daemon |

`Vector` runs the VRL step alone. Its `config` argument is stored but never applied, because there is no sources/transforms/sinks pipeline here. For the full pipeline, run Vector itself.

A Vector config gets checked at two levels, and the difference matters. `validate_config` is in-process and needs no `vector` binary. It compiles the `source` of every `remap` transform and reports each by name. It says nothing about sources, sinks or wiring. Two kinds of VRL come back `unchecked` with a reason rather than failed: an enrichment lookup on a table this process never registered (Vector declares its tables in `enrichment_tables:`, outside VRL), and a call to one of the ten functions the published wheel leaves out.

`validate_config_with_vector` runs `vector validate --no-environment` and checks the lot: wiring, component options, and the VRL the in-process check leaves unchecked. It needs Vector installed, and it's one-shot. Vector exits as soon as it has answered, never running as a daemon and never moving data.

Exact signatures, return shapes, and the rough edges worth knowing (nested objects come back as JSON strings, a per-event runtime error replaces that event's dict) are in [docs/reference-python-api.md](docs/reference-python-api.md).

## Documentation

- [Architecture](docs/architecture.md): the three components, and what caller-supplied VRL can't reach.
- [How to build and test](docs/how-to-build-and-test.md), and [the build orchestrator](docs/how-to-run-the-build-orchestrator.md).
- [Python API reference](docs/reference-python-api.md).

## Issues

Open bugs: [this repo](https://github.com/hyperi-io/vector-vrl/issues?q=is%3Aopen+is%3Aissue+type%3ABug+-label%3Abacklog+-label%3Anext-minor) | [whole DFE suite](https://github.com/search?type=issues&q=is%3Aopen+is%3Aissue+type%3ABug+-label%3Abacklog+-label%3Anext-minor+repo%3Ahyperi-io%2Fdfe-infra+repo%3Ahyperi-io%2Fdfe-docker+repo%3Ahyperi-io%2Fdfe-deploy+repo%3Ahyperi-io%2Fdfe-engine+repo%3Ahyperi-io%2Fdfe-loader+repo%3Ahyperi-io%2Fdfe-receiver+repo%3Ahyperi-io%2Fdfe-fetcher+repo%3Ahyperi-io%2Fdfe-archiver+repo%3Ahyperi-io%2Fdfe-transform-vrl+repo%3Ahyperi-io%2Fdfe-transform-vector+repo%3Ahyperi-io%2Fdfe-transform-elastic+repo%3Ahyperi-io%2Fdfe-ui+repo%3Ahyperi-io%2Fdfe-hyperdx+repo%3Ahyperi-io%2Fscalo-rs+repo%3Ahyperi-io%2Fscalo-py+repo%3Ahyperi-io%2Flogreducer+repo%3Ahyperi-io%2Fdfe-schemas+repo%3Ahyperi-io%2Fvector-vrl+repo%3Ahyperi-io%2Fculvert+repo%3Ahyperi-io%2Fdfe-clickhouse-rs+repo%3Ahyperi-io%2Ffactbook-rs)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Its Context section is the working guide: the layout, the commands that prove a change, and what tends to bite.

## License

Apache License, Version 2.0. See [LICENSE](LICENSE).
