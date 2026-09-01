# vector-vrl

**Vector's own VRL compiler and runtime, compiled into a Python extension.**

[![License](https://img.shields.io/badge/license-Apache--2.0-green)](https://github.com/hyperi-io/vector-vrl/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)

VRL - the [Vector Remap Language](https://vector.dev/docs/reference/vrl/) - is
what makes [Vector](https://vector.dev/) good at logs: parse, filter, redact,
reshape, enrich, in a language built for that and nothing else. The catch has
always been that it only runs inside the `vector` binary.

Not any more, and not by shelling out - the same engine, in your process. 198
of Vector 0.58's 213 VRL functions, zero dependencies.

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
- **AI agents** for VRL processing and development loops - generate a
  candidate, compile it, run it, iterate, all without a Vector install.

## Safer to hand untrusted VRL

Two guards apply to every entry point that compiles VRL:

- **No host, no network.** `get_env_var`, `get_hostname`, `http_request`,
  `dns_lookup` and six more are not compiled in. Caller-supplied VRL cannot
  read your environment or reach out of the process - it fails to compile
  instead. This is what the published wheel ships. Someone building the crate
  from source can turn those ten functions on with the `full-stdlib` Cargo
  feature; only do that where you control the VRL text.
- **No nesting bomb.** VRL source may not nest brackets past 64 levels. Past
  a few hundred the parser's own recursion overflows the stack and kills the
  process, which no Python `except` can catch, so the check runs before the
  parser ever sees the input. There is no way to switch this one off.

That combination is what makes it reasonable to accept VRL from a user - a
multi-tenant playground, a customer-supplied transform, a config someone
pasted in.

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
broken, it reports those transforms as `unchecked` with a reason. YAML needs
`pip install vector-vrl[yaml]`; TOML and JSON need nothing.

`validate_config_with_vector` runs `vector validate --no-environment` and
checks the lot - wiring, component options, and the enrichment-backed VRL the
in-process check has to skip. It needs Vector installed, and it is one-shot:
Vector exits as soon as it has answered, never running as a daemon and never
moving data. `--no-environment` also keeps it offline, so it will not dial your
sinks just to check the file.

Exact signatures, return shapes, and the rough edges worth knowing (nested
objects come back as JSON strings, a per-event runtime error replaces that
event's dict) are in the
[Python API reference](https://github.com/hyperi-io/vector-vrl/blob/main/docs/reference-python-api.md).

## Also in the box

A second surface (`assess_vrl_performance`, `THGPerformanceAssessor`,
`get_apache_combined` and the other pattern helpers) shells out to a `vector`
binary on your PATH instead of using the compiled bindings above. Different
code path, different tests. If you came here for VRL execution, the example at
the top already gave it to you.

## Links

- [Source and issues](https://github.com/hyperi-io/vector-vrl)
- [Architecture](https://github.com/hyperi-io/vector-vrl/blob/main/docs/architecture.md)
- [Building from source](https://github.com/hyperi-io/vector-vrl/blob/main/docs/how-to-build-and-test.md)
  (needs the Rust toolchain - the package wraps a compiled crate)

Apache License, Version 2.0.
