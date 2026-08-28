"""Vector Python bindings accept both YAML and TOML config strings.

Exercises the compiled `vector` PyO3 module directly (no subprocess) -
mirrors the idiom in tests/integration/bindings.py. Skips when the
compiled bindings are not built into the active environment.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

vector = pytest.importorskip("vector")

from vectordotdev.regex2vrl.core import RegexToVRL  # noqa: E402

pytestmark = pytest.mark.integration


def _read_json_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _wait_for_output(path: Path, timeout: float = 5.0) -> list[dict]:
    """Poll the sink's output file until it has content or the timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        results = _read_json_lines(path)
        if results:
            return results
        time.sleep(0.05)
    return _read_json_lines(path)


def test_vector_accepts_yaml_config(tmp_path: Path) -> None:
    """A YAML-format config string is accepted by vector.Vector, same as TOML."""
    output_file = tmp_path / "yaml_config_test.jsonl"
    yaml_config = f"""
sources:
  python:
    type: python
transforms:
  yaml_test:
    type: remap
    inputs: [python]
    source: |
      message_str = string!(.message)
      .yaml_processed = true
      .contains_test = contains(message_str, "test")
sinks:
  file:
    type: file
    inputs: [yaml_test]
    path: "{output_file}"
    encoding:
      codec: json
"""
    v = vector.Vector(yaml_config)
    v.start()
    try:
        v.send("python", json.dumps({"message": "this is a test message"}).encode())
        results = _wait_for_output(output_file)
    finally:
        v.stop()

    assert len(results) == 1, f"expected one processed event, got {results}"
    assert results[0]["yaml_processed"] is True
    assert results[0]["contains_test"] is True


def test_regex2vrl_simple_pattern_via_bindings(tmp_path: Path) -> None:
    """A regex2vrl-generated VRL program runs correctly through the bindings."""
    output_file = tmp_path / "simple_regex2vrl.jsonl"
    vrl_code = RegexToVRL().convert(r"(?P<word>\w+)")

    indented = "\n".join(f"      {line}" for line in vrl_code.split("\n"))
    config = f"""
sources:
  python:
    type: python
transforms:
  simple_regex2vrl:
    type: remap
    inputs: [python]
    source: |
{indented}
sinks:
  file:
    type: file
    inputs: [simple_regex2vrl]
    path: "{output_file}"
    encoding:
      codec: json
"""
    v = vector.Vector(config)
    v.start()
    try:
        v.send("python", json.dumps({"message": "hello world"}).encode())
        results = _wait_for_output(output_file)
    finally:
        v.stop()

    assert len(results) == 1, f"expected regex2vrl output for one event, got {results}"
