"""regex2vrl output actually contains the expected extracted field values.

Goes beyond "did Vector produce any output" - checks specific field
values (including a numeric conversion) via real `vector test` runs, so
a pattern that runs but silently extracts the wrong value is caught.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vectordotdev.regex2vrl.core import RegexToVRL

pytestmark = pytest.mark.integration


def _run_vector_unit_test(vector_runner, tmp_path: Path, vrl_source: str, message: str, condition: str):
    config = {
        "transforms": {"under_test": {"type": "remap", "inputs": [], "source": vrl_source}},
        "tests": [
            {
                "name": "check",
                "input": {"insert_at": "under_test", "type": "raw", "value": message},
                "outputs": [
                    {"extract_from": "under_test", "conditions": [{"type": "vrl", "source": condition}]}
                ],
            }
        ],
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")
    return vector_runner(["test", str(config_path)], tmp_path)


@pytest.mark.parametrize(
    ("pattern", "input_log", "condition"),
    [
        pytest.param(
            r"(?P<ip>\d+\.\d+\.\d+\.\d+)",
            '192.168.1.100 - user [timestamp] "GET /path" 200 1024',
            'exists(.ip) && to_string!(.ip) == "192.168.1.100"',
            id="apache_ip_extraction",
        ),
        pytest.param(
            r"(?P<status>\d{3})",
            "404 status returned to the client",
            "exists(.status) && to_int!(.status) == 404",
            id="status_code_as_int",
        ),
        pytest.param(
            r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}) (?P<level>[A-Z]+) (?P<service>\w+) (?P<message>.*)",
            "2025-01-15T10:30:45 ERROR auth-service Database connection failed",
            (
                'to_string!(.timestamp) == "2025-01-15T10:30:45" '
                '&& to_string!(.level) == "ERROR" '
                '&& to_string!(.service) == "auth-service"'
            ),
            id="multi_field_complex_log",
        ),
        pytest.param(
            r"^(?P<json_data>\{.*\})$",
            '{"level":"INFO","user_id":"12345","message":"Login successful"}',
            # The JSON strategy parses and merges the object's own keys into
            # the event directly, rather than keeping a `.json_data` field.
            '.json_parsed == true && to_string!(.level) == "INFO"',
            id="json_data_extraction",
        ),
    ],
)
def test_field_extraction_matches_expected_value(vector_runner, tmp_path, pattern, input_log, condition):
    """The generated VRL extracts the correct value, not just some value."""
    vrl_code = RegexToVRL().convert(pattern, sample_logs=[input_log])
    result = _run_vector_unit_test(vector_runner, tmp_path, vrl_code, input_log, condition)
    assert result.returncode == 0, (
        f"pattern {pattern!r} on {input_log!r} failed condition {condition!r}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
