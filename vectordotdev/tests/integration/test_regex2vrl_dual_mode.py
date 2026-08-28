"""regex2vrl and grok-to-VRL conversion exercised through both bindings APIs.

Mode 1 - native bindings: `vector.Vector` fed events directly via a
`python` source (in-process, no files).
Mode 2 - CLI emulation: `vector.VectorCliPy` started from a YAML config
file with a `file` source, mirroring how the real CLI would run it.

Both modes use the compiled `vector` PyO3 module and are skipped when
it is not built into the active environment.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import yaml

from vectordotdev.regex2vrl.core import RegexToVRL
from vectordotdev.regex2vrl.grok_converter import GrokToVRL

vector = pytest.importorskip("vector")

pytestmark = pytest.mark.integration


def _convert(pattern: str, pattern_type: str) -> str:
    if pattern_type == "regex":
        return RegexToVRL().convert(pattern)
    return GrokToVRL().convert(pattern)


def _read_json_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _wait_for_output(path: Path, timeout: float = 5.0) -> list[dict]:
    deadline = time.monotonic() + timeout
    results: list[dict] = []
    while time.monotonic() < deadline and not results:
        results = _read_json_lines(path)
        if not results:
            time.sleep(0.05)
    return results


CASES = [
    pytest.param("ip_extraction", r"(?P<ip>\d+\.\d+\.\d+\.\d+)", "regex", "Client IP: 192.168.1.100", id="ip"),
    pytest.param("simple_field", r"(?P<word>\w+)", "regex", "hello world", id="word"),
    pytest.param(
        "syslog",
        "%{SYSLOGBASE} %{GREEDYDATA:message}",
        "grok",
        "Jan 15 10:30:45 server01 sshd[1234]: User login",
        id="syslog_grok",
    ),
]


@pytest.mark.parametrize(("name", "pattern", "pattern_type", "log_line"), CASES)
def test_native_bindings_mode(tmp_path, name, pattern, pattern_type, log_line):
    """Native bindings: python source -> remap transform -> file sink, in-process."""
    vrl_code = _convert(pattern, pattern_type)
    output_file = tmp_path / f"native_{name}.jsonl"
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
  file_output:
    type: file
    inputs: [regex2vrl_transform]
    path: "{output_file}"
    encoding:
      codec: json
"""
    v = vector.Vector(config)
    v.start()
    try:
        v.send("python", json.dumps({"message": log_line, "source": "native_test"}).encode())
        results = _wait_for_output(output_file)
    finally:
        v.stop()

    assert results, f"native bindings produced no output for {name}"


@pytest.mark.parametrize(("name", "pattern", "pattern_type", "log_line"), CASES)
def test_cli_emulation_mode(tmp_path, name, pattern, pattern_type, log_line):
    """CLI emulation: VectorCliPy started from a YAML config file with a file source."""
    vrl_code = _convert(pattern, pattern_type)

    input_file = tmp_path / f"cli_input_{name}.log"
    input_file.write_text(log_line + "\n", encoding="utf-8")

    output_file = tmp_path / f"cli_{name}.jsonl"
    data_dir = tmp_path / "vector_cli_data"
    data_dir.mkdir(exist_ok=True)

    config = {
        "data_dir": str(data_dir),
        "sources": {
            "file_input": {
                "type": "file",
                "include": [str(input_file)],
                "read_from": "beginning",
            }
        },
        "transforms": {
            "regex2vrl_cli": {
                "type": "remap",
                "inputs": ["file_input"],
                "source": vrl_code,
            }
        },
        "sinks": {
            "file_output": {
                "type": "file",
                "inputs": ["regex2vrl_cli"],
                "path": str(output_file),
                "encoding": {"codec": "json"},
            }
        },
    }
    config_file = tmp_path / f"vector_config_{name}.yaml"
    config_file.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")

    cli_vector = vector.VectorCliPy(["--config", str(config_file), "--quiet"])
    cli_vector.start_from_file(str(config_file))
    try:
        results = _wait_for_output(output_file)
    finally:
        cli_vector.stop()

    assert results, f"CLI emulation produced no output for {name}"
