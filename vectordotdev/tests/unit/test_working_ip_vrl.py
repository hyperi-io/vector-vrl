"""IP address extraction VRL: split the message on spaces, take the
second or third token if it is IPv4-shaped.

Runs the VRL program (unchanged from the original) through the
`vector vrl` one-shot subcommand rather than a file-source/sink daemon,
since the daemon never exits on its own.
"""

from __future__ import annotations

import json
from pathlib import Path

VRL_PROGRAM = """
message_str = string!(.message)
parts = split(message_str, " ")

.ip_found = false

if length(parts) > 1 {
    part1 = string!(parts[1])
    if is_ipv4(part1) {
        .ip_address = part1
        .ip_found = true
    }
}

if !.ip_found && length(parts) > 2 {
    part2 = string!(parts[2])
    if is_ipv4(part2) {
        .ip_address = part2
        .ip_found = true
    }
}
"""


def _run_vrl(vector_runner, tmp_path: Path, message: str) -> dict:
    input_file = tmp_path / "input.ndjson"
    input_file.write_text(json.dumps({"message": message}) + "\n", encoding="utf-8")

    program_file = tmp_path / "program.vrl"
    program_file.write_text(VRL_PROGRAM, encoding="utf-8")

    result = vector_runner(
        ["vrl", "--input", str(input_file), "--program", str(program_file), "--print-object"],
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    # vector's own startup log line shares stdout with the printed event;
    # only lines that open a JSON object are output data.
    data_lines = [line for line in result.stdout.splitlines() if line.strip().startswith("{")]
    assert len(data_lines) == 1
    return json.loads(data_lines[0])


def test_ip_found_in_second_word(vector_runner, tmp_path: Path) -> None:
    output = _run_vrl(vector_runner, tmp_path, "Client IP: 192.168.1.100")

    assert output["ip_found"] is True
    assert output["ip_address"] == "192.168.1.100"


def test_no_ip_present_leaves_ip_found_false(vector_runner, tmp_path: Path) -> None:
    output = _run_vrl(vector_runner, tmp_path, "no address in this message at all")

    assert output["ip_found"] is False
    assert "ip_address" not in output
