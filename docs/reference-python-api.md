# Reference: Python API

Everything the compiled extension exposes. Signatures are from
`vector-bindings/src/lib.rs`, behaviour is what the bindings actually do
when called.

Two import paths, same objects:

```python
from vector_vrl import execute_vrl, validate_vrl, get_vrl_performance, Vector, VrlResult
from vector_vrl._bindings import execute_vrl   # equivalent
```

`vector-vrl/__init__.py` re-exports from `._bindings`, falls back to a
top-level `vector_bindings` module, and failing both installs stubs that
raise `ImportError` on call. Check which you got:

```python
import vector_vrl
vector_vrl.get_bindings_info()
# {'available': True, 'source': 'bundled', 'version': '1.0.5', 'bundled': True}
```

`source` is `bundled`, `external` or `none`.

## execute_vrl

```python
execute_vrl(vrl_code: str, input_data: list[str], secrets: dict[str, str] | None = None) -> list[dict]
```

Compiles `vrl_code` once, then runs it over every string in `input_data`.
Returns one dict per input, in order. An empty input list returns an empty
list.

`secrets` seeds every event's secret store before the program runs - see
[Event secrets](#event-secrets). Omit it and each event starts with none.

Raises `ValueError` if the VRL does not compile - that is a whole-batch
failure, because compilation happens before any event is touched. Runtime
errors are per-event and do not raise, see below.

```python
>>> execute_vrl('.level = upcase!(.level)', ['{"level": "info"}'])
[{'level': 'INFO'}]
```

### How input is parsed

If the string starts with `{`, it is parsed as JSON. Anything else - and
any string that starts with `{` but fails to parse - is wrapped as
`{"message": <the raw string>}`.

```python
>>> execute_vrl('.seen = true', ['hello world'])
[{'message': 'hello world', 'seen': True}]
>>> execute_vrl('.seen = true', ['{not json'])
[{'message': '{not json', 'seen': True}]
```

There is no way to tell "this was plain text" from "this was JSON with a
message field" in the output. If that distinction matters, tag it in your
VRL.

### What comes back

The event's top-level fields, flattened into the dict. The VRL program's own
return value is discarded - what you get is the mutated event.

Scalars arrive as native Python types. Nested objects and arrays arrive as
JSON STRINGS, not as dicts and lists:

```python
>>> r = execute_vrl('.obj = {"a": 1}\n.arr = [1,2]\n.n = 3\n.f = 1.5\n.b = true\n.nul = null', ['{"x":1}'])
>>> r[0]
{'arr': '[1,2]', 'b': True, 'f': 1.5, 'n': 3, 'nul': None, 'obj': '{"a":1}', 'x': 1}
```

`json.loads` them yourself if you need the structure. Timestamps and regexes
also come back as strings.

### Per-event errors

A VRL runtime error replaces that event's dict entirely. You get `error` and
`original`, and NOT the event's fields:

```python
>>> execute_vrl('.p = parse_json!(.message)', ['{"message":"nope"}'])
[{'error': 'VRL error: function call error for "parse_json" at (5:26): unable to parse json: ...',
  'original': '{"message":"nope"}'}]
```

Note there is no `success` key here. Detect failure with
`"error" in result`. `Vector.process_logs` returns exactly this shape too.

## Event secrets

Vector attaches a secret store to every event, separate from the event's
fields, and three VRL functions read and write it. All three are compiled in
on every build:

| VRL | Behaviour |
|---|---|
| `get_secret(key)` | The secret's value, or `null` when it is not set. Infallible - no `!` needed |
| `set_secret(key, secret)` | Stores it, replacing any value already under that key. Returns `null` |
| `remove_secret(key)` | Drops it. Removing a key that is not set is not an error |

These match Vector 0.58.0's own semantics. Secrets never appear in the event
dict - they are a separate channel.

```python
>>> execute_vrl('.k = get_secret("api_key")', ['{"x":1}'], {"api_key": "abc123"})
[{'k': 'abc123', 'x': 1}]
```

### execute_vrl_with_secrets

```python
execute_vrl_with_secrets(vrl_code: str, input_data: list[str], secrets: dict[str, str] | None = None) -> list[dict]
```

The same execution as `execute_vrl` - only the return shape differs. Each
entry is a dict of two keys: `event` is exactly what `execute_vrl` would
have returned for that input, and `secrets` is the event's secret store
after the program ran.

```python
>>> execute_vrl_with_secrets('set_secret("token", "s3cr3t")', ['{"x":1}'])
[{'event': {'x': 1}, 'secrets': {'token': 's3cr3t'}}]
```

Secrets are PER EVENT. Every input starts from the same `secrets` argument,
so one event's `set_secret` is invisible to the next:

```python
>>> execute_vrl_with_secrets(
...     'if .n == 1 { set_secret("leak", "yes") }\n.seen = get_secret("leak")',
...     ['{"n":1}', '{"n":2}'],
... )
[{'event': {'n': 1, 'seen': 'yes'}, 'secrets': {'leak': 'yes'}},
 {'event': {'n': 2, 'seen': None}, 'secrets': {}}]
```

An event whose program aborts still reports its secrets, as they stood when
it failed - so `secrets` is populated even alongside an `error` event.

`Vector.process_logs` has no secrets surface: it seeds an empty store and
discards whatever the program left behind.

## validate_vrl

```python
validate_vrl(vrl_code: str) -> VrlResult
```

Compiles without running. Never raises for bad VRL - the failure is in the
returned object. Use it to lint VRL before you ship it.

```python
>>> validate_vrl('.level = upcase!(.level)').success
True
>>> r = validate_vrl('.a = ')
>>> r.success, r.error, r.error_type
(False, 'syntax error', 'compilation_error')
```

## VrlResult

Four read-only attributes:

| Attribute | Type | On success | On failure |
|---|---|---|---|
| `success` | `bool` | `True` | `False` |
| `output` | `str \| None` | `"VRL syntax valid"` | `None` |
| `error` | `str \| None` | `None` | compiler message |
| `error_type` | `str \| None` | `None` | `"compilation_error"` |

`repr()` is Rust's derived `Debug` format, not Python-native - lowercase
`true`/`false` and an `Option` wrapping (`Some("...")` or `None`), not a bare
Python string:

```python
>>> repr(validate_vrl('.level = upcase!(.level)'))
'VrlResult(success=true, output=Some("VRL syntax valid"), error=None)'
```

Only `validate_vrl` returns one - it is not the return type of `execute_vrl`.

## get_vrl_performance

```python
get_vrl_performance(vrl_code: str, test_data: list[str], iterations: int | None = None) -> dict
```

Cycles `test_data` `iterations` times and times the lot. `iterations`
defaults to 100.

```python
>>> m = get_vrl_performance('.a = 1', ['{"x":1}'], iterations=10)
>>> sorted(m)
['events_per_second', 'processing_time_seconds', 'thg_score', 'total_events']
```

`total_events` is `len(test_data) * iterations`. `thg_score` is
`events_per_second` clamped to a 1000 ceiling - it is not an independent
measurement, so two runs above 1000 eps score identically.

`len(test_data) * iterations` is materialised in memory before execution,
so it is capped at 1,000,000. Over that, `ValueError`. Both inputs are
caller-controlled, which is why the cap exists.

This measures the in-process runtime and nothing else. It does not compare
against the `vector` binary.

## Vector

```python
Vector(config: dict)
    .initialize() -> bool
    .process_logs(logs: list[str], vrl_code: str) -> list[dict]
    .get_stats() -> dict
```

A batch VRL runner. Read the constraints below before you build anything on
it.

```python
pipeline = Vector({})
pipeline.initialize()
results = pipeline.process_logs(['{"level":"info"}'], '.level = upcase!(.level)')
```

`config` is round-tripped through Python's `json` module, so anything
`json.dumps` handles is accepted - nested dicts, lists, `True`, `None`,
floats, apostrophes. A value `json` cannot serialise raises `TypeError` or
`ValueError` at construction.

`config` is then STORED AND NEVER USED. It does not affect `initialize` or
`process_logs`. There is no sources/transforms/sinks execution - you can
hand it a full Vector pipeline config and the only thing that runs is the
`vrl_code` argument you pass to `process_logs`. That argument is required
and is not derived from the config.

`initialize()` sets a flag and returns `True`. Calling `process_logs` first
raises `RuntimeError("Vector not initialized")`.

### process_logs return shape

Identical to `execute_vrl` - both go through the same conversion in the
crate. One dict per log, the event's fields flattened in:

```python
{'level': 'INFO'}
```

On a per-event runtime error, `error` and `original` replace the event's
fields:

```python
{'error': 'VRL error: ...', 'original': '<the input string>'}
```

So `"error" in result` is the failure check, the same as `execute_vrl`.
Uncompilable VRL raises `ValueError("VRL compilation failed: ...")` for the
whole batch, also the same as `execute_vrl`.

### get_stats

```python
{'events_processed': 2, 'bytes_processed': 51, 'errors': 1, 'uptime_seconds': 0.31}
```

Real accumulated counts, measured from the most recent `initialize()` -
calling `initialize()` again restarts the uptime clock and zeroes the
counters, so the numbers always describe one run.

| Key | Counts |
|---|---|
| `events_processed` | events `process_logs` transformed without a runtime error |
| `errors` | events that hit a VRL runtime error |
| `bytes_processed` | UTF-8 bytes of every input string handed to `process_logs`, failed events included |
| `uptime_seconds` | seconds since `initialize()`; `0.0` before it is called |

Every event lands in exactly one of `events_processed` or `errors`, so the
two sum to the number of events attempted. VRL that fails to COMPILE raises
before any event is touched and moves no counter.

`config` is still stored and never used - see the constraints above.

## validate_config

```python
validate_config(source: dict | str | Path) -> ConfigCheck
```

Compiles the `source` of every `remap` transform in a Vector config. Runs
in-process against the real compiler, and needs no `vector` binary.

`source` is either an already-parsed dict, or a path to a `.yaml`/`.yml`/
`.toml`/`.json` config. TOML and JSON parse with the stdlib; YAML needs
`pip install vector-vrl[yaml]` and raises `ModuleNotFoundError` naming that
extra otherwise. An unsupported suffix, or a file that does not parse to a
mapping, raises `ValueError`.

```python
>>> r = validate_config({"transforms": {"t": {"type": "remap", "source": ".a = 1"}}})
>>> r.ok
True
```

`ConfigCheck` carries:

| Attribute | Meaning |
|---|---|
| `ok` | every checked transform compiled |
| `checked` | one `TransformCheck` per remap with inline `source` |
| `failures` | the checked ones that did not compile |
| `unchecked` | the checked ones this build could not judge |
| `skipped` | remap transform names whose VRL lives in an external `file:` |

`TransformCheck` is `name`, `ok`, `error`, `unchecked_reason`.

Transforms that are not `type: remap` are ignored entirely. A remap reading
its VRL from `file:` is listed in `skipped` rather than guessed at.

### Why some transforms come back unchecked

Two groups of VRL this build cannot judge on its own:

- `get_enrichment_table_record` and `find_enrichment_table_records` DO
  compile here, but only against a table registered through
  `register_enrichment_table`. Vector declares its tables in
  `enrichment_tables:` outside VRL, so a config naming a table this process
  was never given is unchecked - register it to have it checked.
- The ten functions the sandboxed default build leaves out (`get_env_var`,
  `get_hostname`, `http_request`, `dns_lookup` and six more - see VRL
  restrictions below) report `call to undefined function`.

VRL calling either group is not a broken config, so those transforms come back
with `ok` True and an `unchecked_reason` naming the function, never in
`failures`. Use `validate_config_with_vector` to check them for real.

The event-secret functions used to be in this list. They are compiled in now,
so a config using `get_secret`, `set_secret` or `remove_secret` is checked
like any other - the secret BACKEND is still declared outside VRL and still
invisible here.

## validate_config_with_vector

```python
validate_config_with_vector(
    path: str | Path,
    *,
    vector_binary: str = "vector",
    no_environment: bool = True,
    deny_warnings: bool = False,
    timeout: float = 60.0,
) -> VectorValidation
```

Runs `vector validate` on a config file. Checks everything `validate_config`
cannot - sources, sinks, wiring between components, component options, and the
VRL whose enrichment tables or secrets are declared in the config.

One-shot: Vector exits as soon as it has answered. This never starts a daemon
and never moves data. `no_environment` passes `--no-environment`, skipping the
component and health checks that would open network connections, so checking a
file does not dial the configured sinks.

Raises `FileNotFoundError` when the binary is not on PATH, and
`subprocess.TimeoutExpired` if Vector outlives `timeout`.

`VectorValidation` is `ok`, `returncode`, and `output` - Vector's own report,
which names the offending component on failure.

```python
>>> r = validate_config_with_vector("vector.yaml")
>>> r.ok or r.output
True
```

## VRL restrictions

Two guards apply to every entry point that compiles VRL.

Environment, system and network functions are not compiled in, so
caller-supplied VRL cannot read the host or reach the network. Ten of them
fail to compile with `undefined function`: `get_env_var`, `encode_proto`,
`parse_proto`, `parse_etld`, `validate_json_schema`, `get_hostname`,
`get_timezone_name`, `http_request`, `dns_lookup` and `reverse_dns`. That is
what the published wheel ships; a source build can turn all ten on with the
`full-stdlib` Cargo feature. The reasoning is in
[architecture.md](architecture.md) under "VRL execution's security
posture".

VRL source may not nest brackets more than 64 levels deep
(`MAX_VRL_NESTING_DEPTH`). Past a few hundred the parser's own recursion
overflows the stack and takes the process down, which no Python `except`
can catch, so the check runs before the parser sees the input. Over the
limit you get a message containing `nests`:

```python
>>> validate_vrl('.x = ' + '(' * 1000 + 'true' + ')' * 1000).error
'VRL source nests 1000 levels deep, exceeding the 64-level limit'
```

Both are covered by tests in `vector-bindings/src/lib.rs` and
`vector-vrl/tests/unit/test_vector_class.py`.

## The subprocess surface

`vector_vrl.__all__` also carries `THGPerformanceAssessor`, `THGMetrics`,
`THGResult`, `quick_thg_assessment`, `assess_vrl_performance`,
`execute_vector_pipeline`, `VectorTestRunner`, `ProductionPatterns`,
`production_patterns`, and the `get_apache_combined` / `get_nginx_access` /
`get_json_application` / `get_kubernetes_pods` / `get_docker_container`
pattern helpers.

These are a different thing to everything above. They shell out to a
`vector` BINARY - the first `vector` on PATH, else `/usr/bin/vector`, or
the path you pass - and `VectorTestRunner` raises `RuntimeError` at
construction if no binary exists there. They do not use the compiled
bindings.

They are not part of the in-process API this package is for, and they are
not covered by the test files that describe it. If you want VRL executed,
use `execute_vrl`.
