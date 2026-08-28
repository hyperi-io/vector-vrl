"""Auto-stop timing behaviour of the vector-bindings Vector/VectorCliPy API.

`enable_auto_stop(seconds)` + `wait_until_complete()` should return once
no data has been processed for the configured timeout. Exercises the
compiled `vector_bindings` PyO3 module (a distinct crate/module from
`vector`) and skips when it is not built into the active environment.
"""

from __future__ import annotations

import json
import time

import pytest

from vectordotdev.regex2vrl.core import RegexToVRL

vector_bindings = pytest.importorskip("vector_bindings")

pytestmark = pytest.mark.integration


def test_native_vector_auto_stop(tmp_path):
    """Vector auto-stops ~2s after the last event, and the sink still flushed."""
    output_file = tmp_path / "auto_stop_native_test.jsonl"
    config = f"""
sources:
  python:
    type: python
sinks:
  file:
    type: file
    inputs: [python]
    path: "{output_file}"
    encoding:
      codec: json
"""
    v = vector_bindings.Vector(config)
    v.start()
    v.enable_auto_stop(2.0)

    v.send("python", json.dumps({"message": "auto-stop test", "test": 1}).encode())

    start = time.monotonic()
    v.wait_until_complete(0.1)
    elapsed = time.monotonic() - start

    assert 1.8 <= elapsed <= 3.5, f"expected auto-stop near 2s, took {elapsed:.2f}s"
    assert output_file.exists() and output_file.read_text(encoding="utf-8").strip(), (
        "sink should have flushed the event before auto-stop"
    )


def test_cli_vector_auto_stop(tmp_path):
    """CLI-emulated Vector also honours enable_auto_stop/wait_until_complete."""
    input_file = tmp_path / "cli_auto_stop_input.log"
    input_file.write_text("CLI auto-stop test line 1\nCLI auto-stop test line 2\n", encoding="utf-8")

    output_file = tmp_path / "cli_auto_stop_output.jsonl"
    config_file = tmp_path / "cli_auto_stop_config.toml"
    config_file.write_text(
        f"""
[sources.file_input]
type = "file"
include = ["{input_file}"]
read_from = "beginning"

[sinks.file_output]
type = "file"
inputs = ["file_input"]
path = "{output_file}"
encoding.codec = "json"
""",
        encoding="utf-8",
    )

    cli_v = vector_bindings.VectorCliPy(["--config", str(config_file), "--quiet"])
    cli_v.start_from_file(str(config_file))
    cli_v.enable_auto_stop(3.0)

    start = time.monotonic()
    cli_v.wait_until_complete(0.2)
    elapsed = time.monotonic() - start

    assert 2.5 <= elapsed <= 4.5, f"expected CLI auto-stop near 3s, took {elapsed:.2f}s"


def test_regex2vrl_transform_with_auto_stop(tmp_path):
    """Auto-stop also fires when a regex2vrl-generated remap transform is in the pipeline."""
    vrl_code = RegexToVRL().convert(r"(?P<word>\w+)")
    output_file = tmp_path / "regex2vrl_auto_stop.jsonl"
    indented = "\n".join(f"      {line}" for line in vrl_code.split("\n"))
    config = f"""
sources:
  python:
    type: python
transforms:
  regex2vrl_transform:
    type: remap
    inputs: [python]
    source: |
{indented}
sinks:
  file:
    type: file
    inputs: [regex2vrl_transform]
    path: "{output_file}"
    encoding:
      codec: json
"""
    v = vector_bindings.Vector(config)
    v.start()
    v.enable_auto_stop(1.5)

    v.send("python", json.dumps({"message": "regex2vrl auto-stop test"}).encode())

    start = time.monotonic()
    v.wait_until_complete(0.05)
    elapsed = time.monotonic() - start

    assert 1.2 <= elapsed <= 2.5, f"expected auto-stop near 1.5s, took {elapsed:.2f}s"
