"""Edge cases outside the happy path: VrlResult immutability/repr, and
get_vrl_performance's event-count cap.

No mocks - every case here executes the real compiled bindings.
"""

from __future__ import annotations

import pytest

pytest.importorskip(
    "vector_vrl._bindings",
    reason="compiled PyO3 bindings not built - run: cd vector-bindings && maturin develop --release",
)

from vector_vrl._bindings import get_vrl_performance, validate_vrl  # noqa: E402


class TestVrlResultImmutability:
    """VrlResult is documented as four read-only attributes."""

    def test_success_attribute_is_read_only(self):
        result = validate_vrl(".x = 1")
        with pytest.raises(AttributeError):
            result.success = False

    def test_output_attribute_is_read_only(self):
        result = validate_vrl(".x = 1")
        with pytest.raises(AttributeError):
            result.output = "tampered"

    def test_error_attribute_is_read_only(self):
        result = validate_vrl(".x = 1")
        with pytest.raises(AttributeError):
            result.error = "tampered"

    def test_error_type_attribute_is_read_only(self):
        result = validate_vrl(".x = 1")
        with pytest.raises(AttributeError):
            result.error_type = "tampered"

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
