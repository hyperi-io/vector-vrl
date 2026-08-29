# Reference: Python API

Everything the compiled extension exposes. Signatures are from
`vector-bindings/src/lib.rs`, behaviour is what the bindings actually do
when called.

Two import paths, same objects:

```python
from vectordotdev import execute_vrl, validate_vrl, get_vrl_performance, Vector, VrlResult
from vectordotdev._bindings import execute_vrl   # equivalent
```

`vectordotdev/__init__.py` re-exports from `._bindings`, falls back to a
top-level `vector_bindings` module, and failing both installs stubs that
raise `ImportError` on call. Check which you got:

```python
import vectordotdev
vectordotdev.get_bindings_info()
# {'available': True, 'source': 'bundled', 'version': '1.0.5', 'bundled': True}
```

`source` is `bundled`, `external` or `none`.

## execute_vrl

```python
execute_vrl(vrl_code: str, input_data: list[str]) -> list[dict]
```

Compiles `vrl_code` once, then runs it over every string in `input_data`.
Returns one dict per input, in order. An empty input list returns an empty
list.

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

`repr()` gives `VrlResult(success=..., output=..., error=...)`. Only
`validate_vrl` returns one - it is not the return type of `execute_vrl`.

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

## VRL restrictions

Two guards apply to every entry point that compiles VRL.

Environment and network functions are not compiled in, so caller-supplied
VRL cannot read the host or reach the network. `get_env_var`,
`get_hostname`, `http_request` and `dns_lookup` all fail to compile with
`undefined function`. The reasoning is in
[ARCHITECTURE.md](../ARCHITECTURE.md) under "VRL execution's security
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
`vectordotdev/tests/unit/test_vector_class.py`.

## Auto-discovered classes

The extension also exports one class per public Vector struct or enum found
in the `vector/` checkout at build time - 96 of them in the build this was
written against.

```python
>>> from vectordotdev._bindings import LogEvent
>>> e = LogEvent(); [x for x in dir(e) if not x.startswith('_')]
['data']
```

They are PLACEHOLDERS. Every struct becomes a class with one settable
`data: str` field and no connection to the Rust type it is named after.
Do not build on them. See
[explanation-auto-discovery.md](explanation-auto-discovery.md) and
[issue #15](https://github.com/hyperi-io/vectordotdev/issues/15).

The count is readable at runtime:

```python
>>> from vectordotdev._bindings import vector_bindings
>>> vector_bindings.__auto_count__
96
```

## The subprocess surface

`vectordotdev.__all__` also carries `THGPerformanceAssessor`, `THGMetrics`,
`THGResult`, `quick_thg_assessment`, `assess_vrl_performance`,
`execute_vector_pipeline`, `VectorTestRunner`, `ProductionPatterns`,
`production_patterns`, and the `get_apache_combined` / `get_nginx_access` /
`get_json_application` / `get_kubernetes_pods` / `get_docker_container`
pattern helpers.

These are a different thing to everything above. They shell out to a
`vector` BINARY, defaulting to `/usr/bin/vector`, and `VectorTestRunner`
raises `RuntimeError` at construction if that path does not exist. They do
not use the compiled bindings.

They are not part of the in-process API this package is for, and they are
not covered by the test files that describe it. If you want VRL executed,
use `execute_vrl`.
