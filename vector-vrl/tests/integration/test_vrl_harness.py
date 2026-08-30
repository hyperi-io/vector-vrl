"""In-memory native VRL execution vs real Vector subprocess execution.

`vector_bindings.execute_vrl` (the Rust/PyO3 native executor) should
produce the same number of processed events as a real `vector test` run
of the identical VRL against the identical input logs. Skips the
in-memory half when the compiled `vector_bindings` module is not built
into the active environment; the subprocess half always runs via the
shared vector_runner fixture (real binary or container, no mocks).

Every case's message is a JSON object string, matching `execute_vrl`'s own
rule: a string starting with `{` is parsed and its fields become the
event's top-level fields, not wrapped under `.message`. `vector test`'s
`raw` input type has no such auto-detection - it always wraps the string
under `.message` regardless of content - so the fixture uses `log_fields`
(the already-parsed dict) to put the same top-level fields in front of
both execution paths.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration

vector_bindings = pytest.importorskip("vector_vrl._bindings")


def _run_vector_unit_tests(
    vector_runner, tmp_path: Path, vrl_source: str, cases: list[tuple[str, str, str]]
) -> int:
    """Run one `vector test` per (name, message, condition) case; return the pass count."""
    passed = 0
    for name, message, condition in cases:
        config = {
            "transforms": {
                "under_test": {"type": "remap", "inputs": [], "source": vrl_source}
            },
            "tests": [
                {
                    "name": name,
                    "input": {
                        "insert_at": "under_test",
                        "type": "log",
                        "log_fields": json.loads(message),
                    },
                    "outputs": [
                        {
                            "extract_from": "under_test",
                            "conditions": [{"type": "vrl", "source": condition}],
                        }
                    ],
                }
            ],
        }
        config_path = tmp_path / f"{name}.yaml"
        config_path.write_text(
            yaml.dump(config, default_flow_style=False), encoding="utf-8"
        )
        result = vector_runner(["test", str(config_path)], tmp_path)
        if result.returncode == 0:
            passed += 1
    return passed


@pytest.mark.parametrize(
    ("vrl_code", "cases"),
    [
        pytest.param(
            ".level = upcase!(.level)\n.processed = true",
            [
                (
                    "upcase_info",
                    '{"level": "info", "message": "test"}',
                    ".processed == true",
                ),
                (
                    "upcase_error",
                    '{"level": "error", "message": "error"}',
                    ".processed == true",
                ),
            ],
            id="basic_transform",
        ),
        pytest.param(
            ".user_id = to_int(.user) ?? 0",
            [
                (
                    "user_123",
                    '{"user": "123"}',
                    "is_integer(.user_id) && .user_id == 123",
                ),
                (
                    "user_456",
                    '{"user": "456"}',
                    "is_integer(.user_id) && .user_id == 456",
                ),
            ],
            id="field_operations",
        ),
    ],
)
def test_native_execution_matches_subprocess_count(
    vector_runner, tmp_path, vrl_code, cases
):
    """Native execute_vrl() processes the same number of events as `vector test` passes."""
    memory_results = vector_bindings.execute_vrl(
        vrl_code, [message for _, message, _ in cases]
    )
    subprocess_pass_count = _run_vector_unit_tests(
        vector_runner, tmp_path, vrl_code, cases
    )

    assert len(memory_results) == subprocess_pass_count == len(cases), (
        f"in-memory processed {len(memory_results)}, subprocess passed {subprocess_pass_count}/{len(cases)}"
    )
