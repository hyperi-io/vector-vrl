"""Minimal Vector sanity check: an event survives a no-op VRL program.

Runs `vector vrl` (which exits after one pass) rather than a
file-source/sink daemon, since a daemon never exits on its own.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_event_passes_through_unchanged(vector_runner, tmp_path: Path) -> None:
    input_file = tmp_path / "input.ndjson"
    input_file.write_text(
        json.dumps({"message": "test message"}) + "\n", encoding="utf-8"
    )

    program_file = tmp_path / "program.vrl"
    program_file.write_text(".", encoding="utf-8")

    result = vector_runner(
        [
            "vrl",
            "--input",
            str(input_file),
            "--program",
            str(program_file),
            "--print-object",
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    # vector's own startup log line shares stdout with the printed event;
    # only lines that open a JSON object are output data.
    data_lines = [
        line for line in result.stdout.splitlines() if line.strip().startswith("{")
    ]
    assert len(data_lines) == 1
    output = json.loads(data_lines[0])
    assert output["message"] == "test message"
