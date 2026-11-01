"""`VectorTestRunner` and the THG path drive a real `vector` binary end to end.

The runner's generated config once carried a top-level `log:` block, which
Vector rejects as an unknown field, so every run - and every THG score built
on it - failed before reading a line.
"""

import time

import pytest

from vector_vrl import execute_vector_pipeline
from vector_vrl.vector_test_utils import VectorTestRunner, remap_chain

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


def test_runner_returns_when_vector_finishes_not_after_a_fixed_wait(vector_binary):
    """A fixed sleep before stopping Vector made every run take at least 3 s."""
    runner = VectorTestRunner(vector_binary)

    start = time.perf_counter()
    success, results, error = runner.test_vrl_with_vector(".n = 1", ["{}"], "prompt")
    elapsed = time.perf_counter() - start

    assert success, error
    assert len(results) == 1
    assert elapsed < 3.0, f"took {elapsed:.2f}s"


def test_runner_returns_every_event_of_a_large_batch(vector_binary):
    runner = VectorTestRunner(vector_binary)
    logs = [f'{{"n": {n}}}' for n in range(20_000)]

    success, results, error = runner.test_vrl_with_vector(
        ". = parse_json!(.message)", logs, "large"
    )

    assert success, error
    assert sorted(result["n"] for result in results) == list(range(20_000))


def test_runner_reports_a_run_that_outlives_its_timeout(vector_binary):
    runner = VectorTestRunner(vector_binary)

    success, results, error = runner.test_vrl_with_vector(
        ".n = 1", ["{}"] * 200_000, "slow", timeout=0.01
    )

    assert (success, results) == (False, [])
    assert "did not finish within 0.01s" in error


def test_events_a_program_aborts_are_missing_from_a_successful_run(vector_binary):
    runner = VectorTestRunner(vector_binary)

    success, results, error = runner.test_vrl_with_vector(
        ". = parse_json!(.message)\nif .n == 2 { abort }",
        ['{"n": 1}', '{"n": 2}', '{"n": 3}'],
        "abort",
    )

    assert success, error
    assert [result["n"] for result in results] == [1, 3]


@pytest.mark.parametrize(
    ("config", "message"),
    [
        pytest.param({}, "no transforms", id="empty"),
        pytest.param(
            {"transforms": {"f": {"type": "filter", "condition": "true"}}},
            "not a remap",
            id="filter",
        ),
        pytest.param(
            {"transforms": {"r": {"type": "remap", "file": "x.vrl"}}},
            "no inline source",
            id="file_source",
        ),
        pytest.param(
            {
                "transforms": {
                    "a": {"type": "remap", "source": "."},
                    "b": {"type": "remap", "source": "."},
                }
            },
            "one chain",
            id="unchained",
        ),
        pytest.param(
            {
                "transforms": {
                    "a": {"type": "remap", "source": "."},
                    "b": {"type": "remap", "source": ".", "inputs": ["a"]},
                    "c": {"type": "remap", "source": ".", "inputs": ["a"]},
                }
            },
            "one chain",
            id="fan_out",
        ),
    ],
)
def test_a_pipeline_that_is_not_one_remap_chain_is_refused(config, message):
    with pytest.raises(ValueError, match=message):
        remap_chain(config)


def test_a_pipeline_runs_its_own_remaps_in_input_order(vector_binary):
    """The pipeline once ran the identity program whatever config it was given."""
    config = {
        "sources": {"in": {"type": "stdin"}},
        "transforms": {
            "second": {
                "type": "remap",
                "inputs": ["first"],
                "source": ".order = push(array!(.order), 2)",
            },
            "first": {
                "type": "remap",
                "inputs": ["in"],
                "source": ".order = [1]\n.secret = redact(string!(.message), filters: [r'\\d+'])",
            },
        },
        "sinks": {"out": {"type": "console", "inputs": ["second"]}},
    }

    result = execute_vector_pipeline(config, ["pin 1234"], timeout=30)

    assert result["success"], result["error_message"]
    (event,) = result["results"]
    assert event["order"] == [1, 2]
    assert event["secret"] == "pin [REDACTED]"


def test_benchmark_counts_events_a_program_drops(vector_binary):
    from vector_vrl.thg_performance import THGPerformanceAssessor

    result = THGPerformanceAssessor(vector_binary).assess_pattern_performance(
        "drops",
        ". = parse_json!(.message)\nif .n == 2 { abort }",
        ['{"n": 1}', '{"n": 2}'],
        iterations=5,
    )

    assert result.metrics.total_events_processed == 5
    assert any("5 of 10 events" in line for line in result.recommendations), (
        result.recommendations
    )


def test_benchmark_scores_the_patterns_it_is_given(vector_binary):
    """Two patterns, each a real Vector run."""
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
