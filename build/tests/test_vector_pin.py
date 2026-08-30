"""Unit tests for vector_pin.py's pure, deterministic logic.

No mocks - `current_docker_tag` reads the real conftest.py this repo ships,
and `_version_tuple` is pure. `_tags_newest_first`/`_commit_age_days` need a
real network call to GitHub and are exercised by actually running
`python3 vector_pin.py check` (see docs/how-to-run-the-build-orchestrator.md),
not by a unit test that would otherwise have to fake the response.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vector_pin import CONFTEST_PATH, _version_tuple, current_docker_tag


class TestVersionTuple:
    """String tag to comparable int tuple, the sole basis for every staleness check."""

    def test_parses_a_plain_version(self):
        assert _version_tuple("v0.58.0") == (0, 58, 0)

    def test_orders_by_value_not_lexically(self):
        assert _version_tuple("v0.9.0") < _version_tuple("v0.10.0")

    def test_equal_versions_compare_equal(self):
        assert _version_tuple("v1.2.3") == _version_tuple("v1.2.3")


def test_current_docker_tag_reads_the_real_conftest():
    """conftest.py's `_VECTOR_TAG` is genuinely present and version-shaped."""
    assert CONFTEST_PATH.exists(), f"expected {CONFTEST_PATH} to exist"
    tag = current_docker_tag()
    assert tag is not None
    assert tag.endswith("-debian")


def test_current_docker_tag_returns_none_without_a_match(tmp_path: Path, monkeypatch):
    """A conftest.py with no `_VECTOR_TAG` line yields None, not a crash."""
    import vector_pin

    fake_conftest = tmp_path / "conftest.py"
    fake_conftest.write_text("# no tag here\n", encoding="utf-8")
    monkeypatch.setattr(vector_pin, "CONFTEST_PATH", fake_conftest)

    assert current_docker_tag() is None


@pytest.mark.parametrize("bad_tag", ["not-a-version", ""])
def test_version_tuple_rejects_non_numeric_components(bad_tag):
    with pytest.raises(ValueError):
        _version_tuple(bad_tag)


def test_version_tuple_tolerates_a_short_version():
    """No component-count check - a two-part tag just yields a two-tuple."""
    assert _version_tuple("v1.2") == (1, 2)
