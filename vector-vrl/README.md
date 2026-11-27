# vector-vrl

Vector's own VRL compiler and runtime, in your Python process.

Compile, check and run VRL, the language [Vector](https://vector.dev/) transforms events with, through a compiled Python extension. There's no Vector binary to install and nothing to shell out to. Two things differ from a Vector deployment: the host and network functions are not compiled in, and nested objects and arrays in an event come back as JSON strings.

## What it gives you

- `validate_vrl`, which compiles without running and returns a result rather than raising, so a broken transform fails your test suite instead of your pipeline.
- `execute_vrl`, which compiles once and runs over a batch of events.
- Enrichment tables (CSV and GeoIP) and event secrets, the VRL functions Vector adds on top of the `vrl` crate.
- `validate_config`, which compiles the inline VRL of each `remap` transform in a Vector config, YAML, TOML or JSON, and reports each by name. A transform reading its VRL from `file:` is listed as skipped, and one calling functions only Vector registers is listed as unchecked.
- `validate_config_with_vector`, which runs `vector validate` once for the full check of sources, sinks and wiring, where Vector is installed.
- No host or network functions in the published wheel: `get_env_var`, `get_hostname`, `http_request`, `dns_lookup` and six more fail to compile.
- VRL that nests brackets past 64 levels is refused before the parser sees it, so it cannot overflow the parser's stack and kill your process.
- A `Vector` batch runner that keeps state and stats across calls, for VRL tooling, playgrounds and agent loops.

## Example

```console
uv add vector-vrl
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

Reading a YAML config needs `vector-vrl[yaml]`. TOML and JSON need nothing more.

The function and nesting guards do not bound memory, and the five decompressing functions (`decode_gzip` and its siblings) expand an event with no limit. Where the VRL or the events come from someone who may be hostile, run it in a child process under a memory and a time limit, and treat a dead child as a refused program. The `vector` binary runners have none of these guards, so give them only VRL you trust. The reasoning is at <https://github.com/hyperi-io/vector-vrl/blob/main/docs/architecture.md>.

Docs and source are at <https://github.com/hyperi-io/vector-vrl>, the API reference at <https://github.com/hyperi-io/vector-vrl/blob/main/docs/reference-python-api.md>. Needs Python 3.14 or later. Licensed Apache-2.0: <https://github.com/hyperi-io/vector-vrl/blob/main/LICENSE>.
