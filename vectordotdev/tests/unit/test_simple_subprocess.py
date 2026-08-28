"""Basic VRL transformations run through the `vector vrl` one-shot
subcommand: a field assignment, a string split, and a `now()` call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CASES = [
    pytest.param(
        ".status = \"processed\"",
        "test log message",
        "status",
        "processed",
        id="simple_field_assignment",
    ),
    pytest.param(
        """
        message_str = string!(.message)
        parts = split(message_str, " ")
        if length(parts) > 0 {
            .first_word = parts[0]
        }
        """,
        "hello world test",
        "first_word",
        "hello",
        id="string_split",
    ),
]


def _parse_single_event(stdout: str) -> dict:
    # vector's own startup log line shares stdout with the printed event;
    # only lines that open a JSON object are output data.
    data_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert len(data_lines) == 1
    return json.loads(data_lines[0])


@pytest.mark.parametrize("vrl_program, message, field, expected_value", CASES)
def test_vrl_transformation(
    vector_runner,
    tmp_path: Path,
    vrl_program: str,
    message: str,
    field: str,
    expected_value: str,
) -> None:
    input_file = tmp_path / "input.ndjson"
    input_file.write_text(json.dumps({"message": message}) + "\n", encoding="utf-8")

    program_file = tmp_path / "program.vrl"
    program_file.write_text(vrl_program, encoding="utf-8")

    result = vector_runner(
        ["vrl", "--input", str(input_file), "--program", str(program_file), "--print-object"],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    output = _parse_single_event(result.stdout)
    assert output[field] == expected_value


def test_timestamp_assignment(vector_runner, tmp_path: Path) -> None:
    input_file = tmp_path / "input.ndjson"
    input_file.write_text(json.dumps({"message": "log entry"}) + "\n", encoding="utf-8")

    program_file = tmp_path / "program.vrl"
    # to_string() renders the VRL timestamp type as an RFC 3339 string;
    # the bare `t'...'` literal --print-object emits otherwise is not JSON.
    program_file.write_text(".timestamp = to_string(now())", encoding="utf-8")

    result = vector_runner(
        ["vrl", "--input", str(input_file), "--program", str(program_file), "--print-object"],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    output = _parse_single_event(result.stdout)
    assert "timestamp" in output
