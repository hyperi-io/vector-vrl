"""Unit tests for vector_pin.py's pure, deterministic logic.

No mocks - `current_docker_tag` reads the real conftest.py this repo ships,
and `_version_tuple`, `first_cleared_release` and `pin_image` are pure.
`_tags_newest_first`/`_release_published_at`/`docker_index_digest` need a
real network call to GitHub or Docker Hub and are exercised by actually running `python3 vector_pin.py check`
(see docs/how-to-run-the-build-orchestrator.md), not by a unit test that
would otherwise have to fake the response.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from vector_pin import (
    CONFTEST_PATH,
    DIGEST_RE,
    _version_tuple,
    current_docker_digest,
    current_docker_tag,
    first_cleared_release,
    pin_image,
)


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


def test_current_docker_digest_reads_the_real_conftest():
    """conftest.py's `_VECTOR_DIGEST` is present and a full sha256 digest."""
    digest = current_docker_digest()
    assert digest is not None
    assert DIGEST_RE.match(digest)


def test_current_docker_pins_return_none_without_a_match(tmp_path: Path, monkeypatch):
    """A conftest.py with no pin lines yields None for both, not a crash."""
    import vector_pin

    fake_conftest = tmp_path / "conftest.py"
    fake_conftest.write_text("# no tag here\n", encoding="utf-8")
    monkeypatch.setattr(vector_pin, "CONFTEST_PATH", fake_conftest)

    assert current_docker_tag() is None
    assert current_docker_digest() is None


OLD_DIGEST = "sha256:" + "a" * 64
NEW_DIGEST = "sha256:" + "b" * 64
PIN_SRC = f'_VECTOR_TAG = "0.61.0-debian"\n_VECTOR_DIGEST = "{OLD_DIGEST}"\n'


@pytest.mark.parametrize(
    ("src", "digest", "want"),
    [
        pytest.param(
            PIN_SRC,
            NEW_DIGEST,
            f'_VECTOR_TAG = "0.62.0-debian"\n_VECTOR_DIGEST = "{NEW_DIGEST}"\n',
            id="rewrites_both",
        ),
        pytest.param(
            f'_VECTOR_TAG = "0.61.0-debian"\n_VECTOR_DIGEST = (\n    "{OLD_DIGEST}"\n)\n',
            NEW_DIGEST,
            f'_VECTOR_TAG = "0.62.0-debian"\n_VECTOR_DIGEST = (\n    "{NEW_DIGEST}"\n)\n',
            id="rewrites_a_wrapped_digest",
        ),
        pytest.param(PIN_SRC, "sha256:abc", ValueError, id="short_digest"),
        pytest.param(PIN_SRC, "b" * 64, ValueError, id="digest_without_algorithm"),
        pytest.param(PIN_SRC, "sha256:" + "B" * 64, ValueError, id="uppercase_digest"),
        pytest.param(
            '_VECTOR_TAG = "0.61.0-debian"\n',
            NEW_DIGEST,
            ValueError,
            id="no_digest_line",
        ),
        pytest.param(
            f'_VECTOR_DIGEST = "{OLD_DIGEST}"\n',
            NEW_DIGEST,
            ValueError,
            id="no_tag_line",
        ),
        pytest.param(PIN_SRC + PIN_SRC, NEW_DIGEST, ValueError, id="duplicate_pins"),
    ],
)
def test_pin_image_writes_tag_and_digest_or_refuses(src, digest, want):
    if want is ValueError:
        with pytest.raises(ValueError):
            pin_image(src, "0.62.0-debian", digest)
    else:
        assert pin_image(src, "0.62.0-debian", digest) == want


@pytest.mark.parametrize("bad_tag", ["not-a-version", ""])
def test_version_tuple_rejects_non_numeric_components(bad_tag):
    with pytest.raises(ValueError):
        _version_tuple(bad_tag)


NOW = datetime(2026, 11, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("published", "want"),
    [
        pytest.param(
            [("v0.61.0", "2026-10-29T16:51:24Z"), ("v0.60.0", "2026-10-19T17:55:58Z")],
            "v0.60.0",
            id="newest_too_fresh",
        ),
        pytest.param(
            [("v0.61.0", None), ("v0.60.0", "2026-10-19T17:55:58Z")],
            "v0.60.0",
            id="tag_without_a_release",
        ),
        pytest.param(
            [("v0.60.0", "2026-10-25T00:00:00Z")],
            "v0.60.0",
            id="exactly_seven_days",
        ),
        pytest.param([("v0.61.0", "2026-10-31T00:00:00Z")], None, id="none_cleared"),
        pytest.param([], None, id="no_tags"),
    ],
)
def test_the_cooldown_runs_from_the_release_date(published, want):
    assert first_cleared_release(published, NOW) == want


def test_version_tuple_tolerates_a_short_version():
    """No component-count check - a two-part tag just yields a two-tuple."""
    assert _version_tuple("v1.2") == (1, 2)
