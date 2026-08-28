"""Cross-validate regex2vrl VRL: real Vector subprocess vs Python bindings.

The subprocess run is the ground truth (uses `vector test` against a
config-embedded unit test, via the shared `vector_runner` fixture - a
real Vector binary or container, no mocks). The bindings run exercises
the same generated VRL through the compiled `vector` PyO3 module and is
only checked once the subprocess run has confirmed the VRL itself is
sound.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import yaml

from vectordotdev.regex2vrl.core import RegexToVRL

pytestmark = pytest.mark.integration


def _run_vector_unit_test(vector_runner, tmp_path: Path, vrl_source: str, message: str, condition: str):
    """Run `vector test` against a config with one embedded unit test."""
    config = {
        "transforms": {
            "under_test": {
                "type": "remap",
                "inputs": [],
                "source": vrl_source,
            }
        },
        "tests": [
            {
                "name": "check",
                "input": {"insert_at": "under_test", "type": "raw", "value": message},
                "outputs": [
                    {
                        "extract_from": "under_test",
                        "conditions": [{"type": "vrl", "source": condition}],
                    }
                ],
            }
        ],
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")
    return vector_runner(["test", str(config_path)], tmp_path)


def _read_json_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


@pytest.mark.parametrize(
    ("pattern", "message", "condition"),
    [
        pytest.param(
            r"(?P<ip>\d+\.\d+\.\d+\.\d+)",
            "192.168.1.100 connected as client",
            'exists(.ip) && to_string!(.ip) == "192.168.1.100"',
            id="ip_extraction",
        ),
        pytest.param(
            r"(?P<word>\w+)",
            "hello world",
            "exists(.word)",
            id="simple_word",
        ),
    ],
)
def test_regex2vrl_ground_truth_via_subprocess(vector_runner, tmp_path, pattern, message, condition):
    """The generated VRL passes a real `vector test` run (ground truth)."""
    vrl_code = RegexToVRL().convert(pattern)
    result = _run_vector_unit_test(vector_runner, tmp_path, vrl_code, message, condition)
    assert result.returncode == 0, (
        f"vector test failed for pattern {pattern!r}: stdout={result.stdout} stderr={result.stderr}"
    )


@pytest.mark.parametrize(
    ("pattern", "message"),
    [
        pytest.param(r"(?P<ip>\d+\.\d+\.\d+\.\d+)", "192.168.1.100 connected as client", id="ip_extraction"),
        pytest.param(r"(?P<word>\w+)", "hello world", id="simple_word"),
    ],
)
def test_regex2vrl_bindings_match_subprocess(vector_runner, tmp_path, pattern, message):
    """Once ground truth is confirmed, the same VRL also produces output via bindings."""
    vector = pytest.importorskip("vector")

    vrl_code = RegexToVRL().convert(pattern)
    ground_truth = _run_vector_unit_test(vector_runner, tmp_path, vrl_code, message, "exists(.message)")
    assert ground_truth.returncode == 0, "subprocess ground-truth check must pass before bindings are tested"

    output_file = tmp_path / "bindings_output.jsonl"
    indented = "\n".join(f"      {line}" for line in vrl_code.split("\n"))
    config = f"""
sources:
  python:
    type: python
transforms:
  test_transform:
    type: remap
    inputs: [python]
    source: |
{indented}
sinks:
  file:
    type: file
    inputs: [test_transform]
    path: "{output_file}"
    encoding:
      codec: json
"""
    v = vector.Vector(config)
    v.start()
    try:
        v.send("python", json.dumps({"message": message}).encode())
        deadline = time.monotonic() + 5.0
        results: list[dict] = []
        while time.monotonic() < deadline and not results:
            results = _read_json_lines(output_file)
            if not results:
                time.sleep(0.05)
    finally:
        v.stop()

    assert len(results) == 1, f"expected bindings to process the event, got {results}"
