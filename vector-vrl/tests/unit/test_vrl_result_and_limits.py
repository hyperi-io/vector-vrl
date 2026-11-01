"""Edge cases outside the happy path: VrlResult immutability/repr, and
get_vrl_performance's event-count cap.

No mocks - every case here executes the real compiled bindings.
"""

from __future__ import annotations

import itertools
import subprocess
import sys
import threading
import time

import pytest

pytest.importorskip(
    "vector_vrl._bindings",
    reason="compiled PyO3 bindings not built - run: cd vector-bindings && maturin develop --release",
)

from vector_vrl._bindings import (  # noqa: E402
    Vector,
    execute_vrl,
    execute_vrl_with_secrets,
    get_vrl_performance,
    validate_vrl,
)


def _run_python(script: str) -> subprocess.CompletedProcess[str]:
    """Run `script` in a fresh interpreter, so an abort fails one test, not the run."""
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


class TestVrlResultImmutability:
    """VrlResult is documented as four read-only attributes."""

    def test_success_attribute_is_read_only(self):
        result = validate_vrl(".x = 1")
        with pytest.raises(AttributeError):
            result.success = False  # ty: ignore[invalid-assignment]

    def test_output_attribute_is_read_only(self):
        result = validate_vrl(".x = 1")
        with pytest.raises(AttributeError):
            result.output = "tampered"  # ty: ignore[invalid-assignment]

    def test_error_attribute_is_read_only(self):
        result = validate_vrl(".x = 1")
        with pytest.raises(AttributeError):
            result.error = "tampered"  # ty: ignore[invalid-assignment]

    def test_error_type_attribute_is_read_only(self):
        result = validate_vrl(".x = 1")
        with pytest.raises(AttributeError):
            result.error_type = "tampered"  # ty: ignore[invalid-assignment]

    def test_repr_on_success(self):
        """repr() is Rust's derived Debug format, not Python-native - lowercase
        `true` and `Some(...)` wrapping an Option, not `True`/a bare string."""
        ok = validate_vrl(".x = 1")
        assert (
            repr(ok)
            == 'VrlResult(success=true, output=Some("VRL syntax valid"), error=None)'
        )

    def test_repr_on_failure(self):
        bad = validate_vrl(".x = ")
        assert repr(bad).startswith("VrlResult(success=false, output=None, error=Some(")


class TestGetVrlPerformanceCap:
    """test_data.len() * iterations is capped at 1,000,000 (docs/reference-python-api.md)."""

    def test_exactly_at_the_cap_is_accepted(self):
        metrics = get_vrl_performance(
            ".processed = true", ['{"a":1}'], iterations=1_000_000
        )
        assert metrics["total_events"] == 1_000_000

    def test_one_past_the_cap_is_rejected(self):
        with pytest.raises(ValueError, match="1000001"):
            get_vrl_performance(".processed = true", ['{"a":1}'], iterations=1_000_001)

    def test_cap_is_the_product_not_either_factor_alone(self):
        """Neither factor alone is over the cap - only their product is."""
        with pytest.raises(ValueError, match="exceeds the 1000000 limit"):
            get_vrl_performance(".processed = true", ["{}"] * 2_000, iterations=1_000)

    def test_memory_does_not_grow_with_iterations(self):
        """1,000 iterations of a 2 MB event is 2 GB if the repeats are built up front."""
        result = _run_python(
            "import resource, sys\n"
            "from vector_vrl import get_vrl_performance\n"
            "get_vrl_performance('.y = 1', ['x' * 2_000_000], iterations=1_000)\n"
            "peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss\n"
            "print(peak // (1024 * 1024) if sys.platform == 'darwin' else peak // 1024)\n"
        )
        assert result.returncode == 0, result.stderr
        assert int(result.stdout) < 500, (
            f"peak resident memory {result.stdout.strip()} MB"
        )


class TestEventsTheVrlEngineMustNotMangle:
    """Output a JSON-shaped result cannot hold fails the event instead of being rewritten."""

    def test_an_infinite_float_fails_its_event_instead_of_becoming_zero(self):
        events = ['{"message": "1e999"}', '{"message": "2.5"}']

        infinite, finite = execute_vrl(".x = parse_float!(.message)", events)

        assert infinite["original"] == events[0]
        assert "`.x` is an infinite float" in infinite["error"]
        assert finite == {"message": "2.5", "x": 2.5}

    def test_an_infinite_float_counts_as_an_error_in_the_pipeline_stats(self):
        pipeline = Vector({})
        pipeline.initialize()

        pipeline.process_logs(
            ['{"message": "1e999"}', '{"message": "2.5"}'],
            ".x = parse_float!(.message)",
        )

        stats = pipeline.get_stats()
        assert (stats["events_processed"], stats["errors"]) == (1, 1)

    def test_an_infinite_float_nested_in_the_event_is_found_too(self):
        (result,) = execute_vrl(
            '.n = {"a": [1.5, parse_float!("1e999")]}', ['{"message": "m"}']
        )

        assert "`.n.a[1]` is an infinite float" in result["error"]

    @pytest.mark.parametrize(
        ("vrl", "kind"),
        [(". = [1, 2]", "array"), ('. = "value"', "string")],
        ids=["array", "string"],
    )
    def test_a_non_object_event_fails_instead_of_coming_back_empty(self, vrl, kind):
        pipeline = Vector({})
        pipeline.initialize()

        (result,) = pipeline.process_logs(['{"message": "m"}'], vrl)

        assert f"set the event to a {kind}" in result["error"]
        stats = pipeline.get_stats()
        assert (stats["events_processed"], stats["errors"]) == (0, 1)

    @pytest.mark.parametrize(
        ("event", "outcome"),
        [
            ('{"id": 18446744073709551615}', "`.id` holds 18446744073709551615"),
            ('{"id": 9223372036854775807}', 9223372036854775807),
            ('{"id": -9223372036854775808}', -9223372036854775808),
        ],
        ids=["above_i64", "i64_max", "i64_min"],
    )
    def test_an_integer_is_kept_exactly_or_its_event_fails(self, event, outcome):
        (result,) = execute_vrl(".seen = true", [event])

        if isinstance(outcome, str):
            assert outcome in result["error"]
        else:
            assert result == {"id": outcome, "seen": True}


def _longest_stall_of_another_thread(call) -> tuple[float, float]:
    """Run `call` while a second thread ticks every millisecond.

    Returns the call's duration and the longest gap between ticks during it.
    A call holding the GIL stalls the ticking thread for its whole duration.
    """
    ticks: list[float] = []
    stop = threading.Event()

    def tick() -> None:
        while not stop.is_set():
            ticks.append(time.perf_counter())
            time.sleep(0.001)

    ticker = threading.Thread(target=tick)
    ticker.start()
    try:
        time.sleep(0.01)
        start = time.perf_counter()
        call()
        end = time.perf_counter()
    finally:
        stop.set()
        ticker.join()
    inside = [start, *(t for t in ticks if start < t < end), end]
    return end - start, max(b - a for a, b in itertools.pairwise(inside))


def _chain(depth: int) -> str:
    return ".x = " + "1 + " * depth + "1"


def _initialized_vector() -> Vector:
    pipeline = Vector({})
    pipeline.initialize()
    return pipeline


class TestGilRelease:
    """Compiling and running VRL leaves the GIL free for other Python threads."""

    @pytest.mark.parametrize(
        "make_call",
        [
            pytest.param(
                lambda size: (
                    lambda: get_vrl_performance(
                        ".y = 1", ['{"a":1}'], iterations=size * 500
                    )
                ),
                id="get_vrl_performance",
            ),
            pytest.param(
                lambda size: lambda: validate_vrl(_chain(size)), id="validate_vrl"
            ),
            pytest.param(
                lambda size: lambda: execute_vrl(_chain(size), ["{}"]),
                id="execute_vrl",
            ),
            pytest.param(
                lambda size: lambda: execute_vrl_with_secrets(_chain(size), ["{}"]),
                id="execute_vrl_with_secrets",
            ),
            pytest.param(
                lambda size: (
                    lambda: _initialized_vector().process_logs(["{}"], _chain(size))
                ),
                id="process_logs",
            ),
        ],
    )
    def test_another_thread_keeps_running_during_the_call(self, make_call):
        size = 100
        duration, stall = _longest_stall_of_another_thread(make_call(size))
        while duration < 0.2 and size < 4000:
            size *= 2
            duration, stall = _longest_stall_of_another_thread(make_call(size))

        assert duration >= 0.2, f"size {size} still ran in {duration:.3f}s"
        assert stall < duration / 2, (
            f"another thread stalled {stall:.3f}s of a {duration:.3f}s call"
        )

    def test_threads_sharing_one_pipeline_all_land_in_its_stats(self):
        pipeline = _initialized_vector()
        failures: list[BaseException] = []

        def work() -> None:
            try:
                for _ in range(20):
                    pipeline.process_logs(['{"a": 1}', "plain"], _chain(50))
            except BaseException as error:  # noqa: BLE001 -- reported below
                failures.append(error)

        workers = [threading.Thread(target=work) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        assert failures == []
        stats = pipeline.get_stats()
        assert (stats["events_processed"], stats["errors"]) == (160, 0)
        assert stats["bytes_processed"] == 4 * 20 * (len('{"a": 1}') + len("plain"))


class TestCallerStack:
    """Compiling must not depend on how much stack the calling thread has."""

    @pytest.mark.parametrize(
        "vrl",
        ["1 + " * 300 + "1", "!" * 300 + "true", "true && " * 300 + "true"],
        ids=["sum", "not", "and"],
    )
    def test_an_operator_chain_compiles_on_a_small_thread(self, vrl: str):
        """None of these nests a bracket, so the 64-level bracket limit lets them through."""
        result = _run_python(
            "import threading\n"
            "from vector_vrl import execute_vrl, validate_vrl\n"
            "threading.stack_size(256 * 1024)\n"
            "outcome = []\n"
            "def work():\n"
            f"    source = '.x = ' + {vrl!r}\n"
            "    outcome.append(validate_vrl(source).success)\n"
            "    outcome.append('x' in execute_vrl(source, ['{}'])[0])\n"
            "thread = threading.Thread(target=work)\n"
            "thread.start()\n"
            "thread.join()\n"
            "assert outcome == [True, True], outcome\n"
        )
        assert result.returncode == 0, result.stderr
