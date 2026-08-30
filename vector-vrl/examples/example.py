"""Minimal end-to-end example of vector_vrl's real public API.

Everything here is synchronous and in-process - there is no streaming
pipeline, no `.start()`/`.send()`/`.stop()` lifecycle, and no `vector`
top-level module. The three entry points below are what the compiled
extension actually exposes; see README.md and docs/reference-python-api.md
for the full reference.
"""

import json

from vector_vrl import Vector, execute_vrl, validate_vrl

vrl = """
parsed, err = parse_json(.message)
if err == null {
    .level = parsed.level
}
"""

# validate_vrl compiles without running - use it to lint VRL before shipping it.
check = validate_vrl(vrl)
print("VRL compiles:", check.success)

# execute_vrl compiles once, then runs it over every string in the input list.
events = [json.dumps({"message": json.dumps({"level": "info"})})]
print("execute_vrl:", execute_vrl(vrl, events))

# Vector is a batch runner over the same compiler - initialize() first.
pipeline = Vector({})
pipeline.initialize()
results = pipeline.process_logs(['{"level":"info"}'], ".level = upcase!(.level)")
print("Vector.process_logs:", results)
print("Vector.get_stats:", pipeline.get_stats())
