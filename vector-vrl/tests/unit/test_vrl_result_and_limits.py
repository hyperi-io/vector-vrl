"""Edge cases outside the happy path: VrlResult immutability/repr, and
get_vrl_performance's event-count cap.

No mocks - every case here executes the real compiled bindings.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

pytest.importorskip(
    "vector_vrl._bindings",
    reason="compiled PyO3 bindings not built - run: cd vector-bindings && maturin develop --release",
)

from vector_vrl._bindings import (  # noqa: E402
    Vector,
    execute_vrl,
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
