"""`VectorTestRunner` and the THG path drive a real `vector` binary end to end.

The runner's generated config once carried a top-level `log:` block, which
Vector rejects as an unknown field, so every run - and every THG score built
on it - failed before reading a line.
"""

import pytest

from vector_vrl.vector_test_utils import VectorTestRunner

pytestmark = pytest.mark.integration


def test_runner_processes_logs_through_the_real_binary(vector_binary):
    runner = VectorTestRunner(vector_binary)

    success, results, error = runner.test_vrl_with_vector(
        ".flag = true", ['{"a": 1}', '{"a": 2}'], "runner_smoke"
    )

    assert success, error
    assert len(results) == 2
    assert all(result["flag"] is True for result in results)


def test_runner_reports_a_config_that_vector_rejects(vector_binary):
    runner = VectorTestRunner(vector_binary)

    success, results, error = runner.test_vrl_with_vector(
        ".x = no_such_function!()", ['{"a": 1}'], "runner_bad_vrl"
    )

    assert not success
    assert results == []
    assert "no_such_function" in error


def test_runner_finds_the_binary_on_path_by_default(vector_binary):
    assert VectorTestRunner().vector_binary == vector_binary


def test_benchmark_scores_the_patterns_it_is_given(vector_binary):
    """Two patterns keep the fixed per-run wait to a few seconds."""
    pytest.importorskip("yaml")
    from vector_vrl.production_patterns import ProductionPatterns

    logs = {
        "apache_combined": [
            '1.2.3.4 - u [01/Jan/2026:00:00:00 +0000] "GET / HTTP/1.1" 200 1'
        ],
        "json_application": ['{"level": "INFO", "message": "ok"}'],
    }

    results = ProductionPatterns.benchmark_all_patterns(logs)

    assert set(results) == set(logs)
    for name, result in results.items():
        assert "error" not in result, f"{name}: {result}"
        assert result["thg_score"] > 0
