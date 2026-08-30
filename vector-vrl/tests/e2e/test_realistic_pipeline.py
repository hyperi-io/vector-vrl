"""A realistic multi-branch VRL pipeline, end to end.

Parses a JSON-encoded `.message`, classifies HTTP-style status codes into
tiers, and isolates malformed input instead of raising - the shape of a
real log-processing transform, not a single-field toy case. Runs the same
VRL through the native in-process executor and a real `vector test`
container, and checks they agree - happy path AND the malformed-input
edge case together, since a pipeline that only agrees on well-formed
input is not proven end to end.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.e2e

vector_bindings = pytest.importorskip("vector_vrl._bindings")

PIPELINE_VRL = """
parsed, err = parse_json(.message)
if err != null {
    .error = "malformed_input"
} else {
    .user_id = parsed.user_id
    status = to_int!(parsed.status)
    .status = status
    if status >= 500 {
        .tier = "server_error"
    } else if status >= 400 {
        .tier = "client_error"
    } else {
        .tier = "ok"
    }
}
"""

# (name, message field value, VRL condition the real Vector output must satisfy)
CASES = [
    (
        "ok_case",
        json.dumps({"user_id": 1, "status": 200}),
        '.tier == "ok" && .user_id == 1',
    ),
    (
        "client_error_case",
        json.dumps({"user_id": 2, "status": 404}),
        '.tier == "client_error" && .status == 404',
    ),
    (
        "server_error_case",
        json.dumps({"user_id": 3, "status": 503}),
        '.tier == "server_error" && .status == 503',
    ),
    ("malformed_case", "not json at all", '.error == "malformed_input"'),
]


def test_native_classification_matches_documented_shape():
    """The native path classifies every tier correctly and isolates the malformed event."""
    events = [json.dumps({"message": message}) for _, message, _ in CASES]
    results = vector_bindings.execute_vrl(PIPELINE_VRL, events)

    assert results[0] == {
        "message": CASES[0][1],
        "user_id": 1,
        "status": 200,
        "tier": "ok",
    }
    assert results[1] == {
        "message": CASES[1][1],
        "user_id": 2,
        "status": 404,
        "tier": "client_error",
    }
    assert results[2] == {
        "message": CASES[2][1],
        "user_id": 3,
        "status": 503,
        "tier": "server_error",
    }
    assert results[3] == {"message": "not json at all", "error": "malformed_input"}


def test_real_vector_agrees_with_native_on_every_case(vector_runner, tmp_path: Path):
    """A real `vector test` run reaches the same tier/error classification per case."""
    config = {
        "transforms": {
            "under_test": {"type": "remap", "inputs": [], "source": PIPELINE_VRL}
        },
        "tests": [
            {
                "name": name,
                "input": {
                    "insert_at": "under_test",
                    "type": "log",
                    "log_fields": {"message": message},
                },
                "outputs": [
                    {
                        "extract_from": "under_test",
                        "conditions": [{"type": "vrl", "source": condition}],
                    }
                ],
            }
            for name, message, condition in CASES
        ],
    }
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        yaml.dump(config, default_flow_style=False), encoding="utf-8"
    )

    result = vector_runner(["test", str(config_path)], tmp_path)

    assert result.returncode == 0, (
        f"real Vector disagreed with the native classification on at least one case:\n{result.stdout}\n{result.stderr}"
    )
