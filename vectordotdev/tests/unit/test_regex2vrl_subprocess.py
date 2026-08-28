"""regex2vrl -> VRL -> Vector: convert a regex pattern with `RegexToVRL`,
run the generated VRL through the real `vector vrl` subcommand, and
check the named capture groups show up as fields on the output event.

Uses the real `RegexToVRL` implementation only - no mocking of the
converter itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vectordotdev.regex2vrl.core import RegexToVRL

CASES = [
    pytest.param(
        r"(?P<ip>\d+\.\d+\.\d+\.\d+)",
        [
            "Client IP: 192.168.1.100",
            "Server: 10.0.0.1 active",
            "Gateway 172.16.0.1 online",
        ],
        ["ip"],
        id="ip_extraction",
    ),
    pytest.param(
        r'^(?P<json_data>\{.*\})$',
        [
            '{"level":"INFO","message":"Test","id":123}',
            '{"level":"ERROR","message":"Failed","code":500}',
        ],
        ["json_data"],
        id="json_parsing",
    ),
    pytest.param(
        r'^(?P<ip>\d+\.\d+\.\d+\.\d+) - (?P<user>\S+) \[(?P<timestamp>[^\]]+)\] "(?P<method>\w+)',
        [
            '192.168.1.100 - john [15/Jan/2025:10:30:45 +0000] "GET /index.html',
            '10.0.0.1 - admin [15/Jan/2025:10:30:46 +0000] "POST /api/data',
        ],
        ["ip", "user", "timestamp", "method"],
        id="apache_log",
    ),
    pytest.param(
        r'^(?P<timestamp>\w{3} \d{1,2} \d{2}:\d{2}:\d{2}) (?P<hostname>\S+) (?P<program>\w+)',
        [
            "Jan 15 10:30:45 server01 sshd[1234]: User login",
            "Jan 15 10:30:46 web-server nginx: Process started",
        ],
        ["timestamp", "hostname", "program"],
        id="syslog",
    ),
]


@pytest.mark.parametrize("pattern, logs, expected_fields", CASES)
def test_regex_pattern_extracts_expected_fields(
    vector_runner,
    tmp_path: Path,
    pattern: str,
    logs: list[str],
    expected_fields: list[str],
) -> None:
    vrl_code = RegexToVRL().convert(pattern, output_format="vrl")

    input_file = tmp_path / "input.ndjson"
    input_file.write_text(
        "\n".join(json.dumps({"message": log}) for log in logs) + "\n", encoding="utf-8"
    )
    program_file = tmp_path / "program.vrl"
    program_file.write_text(vrl_code, encoding="utf-8")

    result = vector_runner(
        ["vrl", "--input", str(input_file), "--program", str(program_file), "--print-object"],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    # vector's own startup log line shares stdout with the printed events;
    # only lines that open a JSON object are output data.
    data_lines = [line for line in result.stdout.splitlines() if line.strip().startswith("{")]
    assert len(data_lines) == len(logs)

    outputs = [json.loads(line) for line in data_lines]
    for field in expected_fields:
        assert any(field in event for event in outputs), (
            f"Expected field {field!r} not found in any output event: {outputs}"
        )
