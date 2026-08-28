"""regex2vrl / grok2vrl -> VRL -> Vector integration: convert a pattern
with the real converter, run the generated VRL through `vector vrl`, and
check the named capture groups show up as fields on the output event.

Overlaps test_regex2vrl_subprocess.py's regex cases; this file adds the
grok and timestamp-extraction patterns and is the superset of the two -
worth consolidating in a follow-up.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vectordotdev.regex2vrl.core import RegexToVRL
from vectordotdev.regex2vrl.grok_converter import GrokToVRL

REGEX_CASES = [
    pytest.param(
        r'^(?P<ip>\d+\.\d+\.\d+\.\d+) - (?P<user>\S+) \[(?P<timestamp>[^\]]+)\] '
        r'"(?P<method>\w+) (?P<path>[^\s"]+) HTTP/(?P<version>[\d\.]+)" '
        r'(?P<status>\d{3}) (?P<size>\d+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"',
        [
            '192.168.1.100 - john [15/Jan/2025:10:30:45 +0000] "GET /index.html HTTP/1.1" '
            '200 1024 "https://google.com" "Mozilla/5.0"',
            '10.0.0.1 - - [15/Jan/2025:10:30:46 +0000] "POST /api/data HTTP/1.1" '
            '201 512 "-" "curl/7.68.0"',
        ],
        ["ip", "method", "status", "path"],
        id="apache_combined_integration",
    ),
    pytest.param(
        r'^(?P<json_data>\{.*\})$',
        [
            '{"timestamp":"2025-01-15T10:30:45Z","level":"INFO","message":"User login","user_id":"12345"}',
            '{"timestamp":"2025-01-15T10:30:46Z","level":"ERROR","message":"Database error","error_code":500}',
        ],
        ["json_data"],
        id="json_app_integration",
    ),
    pytest.param(
        r'^(?P<month>\w{3}) (?P<day>\d{1,2}) (?P<time>\d{2}:\d{2}:\d{2}) (?P<hostname>\S+) '
        r'(?P<program>\w+)(?:\[(?P<pid>\d+)\])?: (?P<message>.*)$',
        [
            "Jan 15 10:30:45 server01 sshd[1234]: Accepted password for john from 192.168.1.100",
            "Jan 15 10:30:46 web-server nginx: worker process started",
        ],
        ["hostname", "program", "message"],
        id="syslog_integration",
    ),
    pytest.param(
        r"IP:\s*(?P<ip_address>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})",
        [
            "Client IP: 192.168.1.100",
            "Server IP: 10.0.0.1",
            "Gateway IP: 172.16.0.1",
        ],
        ["ip_address"],
        id="ip_extraction_integration",
    ),
    pytest.param(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z?) (?P<level>\w+) (?P<message>.*)$',
        [
            "2025-01-15T10:30:45.123Z INFO Application started successfully",
            "2025-01-15T10:30:46Z ERROR Database connection failed",
        ],
        ["timestamp", "level", "message"],
        id="timestamp_extraction_integration",
    ),
]


def _run_vrl_over_logs(vector_runner, tmp_path: Path, vrl_code: str, logs: list[str]) -> list[dict]:
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
    return [json.loads(line) for line in data_lines]


@pytest.mark.parametrize("pattern, logs, expected_fields", REGEX_CASES)
def test_regex_pattern_integration(
    vector_runner,
    tmp_path: Path,
    pattern: str,
    logs: list[str],
    expected_fields: list[str],
) -> None:
    vrl_code = RegexToVRL().convert(pattern, output_format="commented")

    outputs = _run_vrl_over_logs(vector_runner, tmp_path, vrl_code, logs)

    assert len(outputs) == len(logs)
    for field in expected_fields:
        assert any(field in event for event in outputs), (
            f"Expected field {field!r} not found in any output event: {outputs}"
        )


def test_grok_apache_pattern_integration(vector_runner, tmp_path: Path) -> None:
    grok_pattern = "%{COMBINEDAPACHELOG}"
    logs = [
        '192.168.1.100 - frank [10/Oct/2025:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" '
        '200 2326 "http://www.example.com/start.html" "Mozilla/4.08 [en]"'
    ]
    expected_fields = ["clientip", "verb", "response"]

    vrl_code = GrokToVRL().convert(grok_pattern)

    outputs = _run_vrl_over_logs(vector_runner, tmp_path, vrl_code, logs)

    assert len(outputs) == len(logs)
    for field in expected_fields:
        assert any(field in event for event in outputs), (
            f"Expected field {field!r} not found in any output event: {outputs}"
        )
