"""Every VRL function Vector exposes, checked against what this build compiles.

The question this answers is "can someone paste vector.dev VRL in here and have
it work", turned into something CI decides on every run rather than something a
human re-audits occasionally.

Checks run in BOTH directions. A function that stops compiling fails, and so
does one that starts compiling while still listed as excluded - otherwise the
exclusion list rots into a claim nobody has tested. The expectation table is
tests/data/vector_vrl_functions.tsv.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vector_vrl import validate_vrl

TABLE = Path(__file__).parent.parent / "data" / "vector_vrl_functions.tsv"

# The full-stdlib Cargo feature decides whether the env/system/network
# functions are compiled in, and the wheel does not advertise which build it
# is. Probe one of them and let the answer pick the expectation.
_FEATURE_PROBE = "get_env_var"


def _rows() -> list[tuple[str, str, str]]:
    rows = []
    for line in TABLE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, status, *rest = line.split("\t")
        rows.append((name, status, rest[0] if rest else ""))
    return rows


ROWS = _rows()


def _is_undefined(name: str) -> bool:
    """Report whether this build has no such function.

    A call with no arguments is enough: an existing function complains about
    the missing argument, a missing one about the function itself.
    """
    result = validate_vrl(f"{name}()")
    return not result.success and "undefined function" in (result.error or "")


FULL_STDLIB = not _is_undefined(_FEATURE_PROBE)


def test_the_probe_distinguishes_missing_from_misused():
    """The whole suite rests on this distinction, so assert it directly."""
    assert _is_undefined("definitely_not_a_vrl_function_xyz")
    assert not _is_undefined("parse_json")


def test_the_table_covers_vectors_whole_surface():
    """Guards against the table being truncated or silently regenerated small."""
    assert len(ROWS) == 213, f"expected Vector 0.58.0's 213 functions, got {len(ROWS)}"
    statuses = {status for _, status, _ in ROWS}
    assert statuses <= {"supported", "feature:full-stdlib", "unsupported"}


@pytest.mark.parametrize(
    ("name", "status", "reason"),
    ROWS,
    ids=[f"{name}-{status}" for name, status, _ in ROWS],
)
def test_function_matches_its_declared_status(name: str, status: str, reason: str):
    undefined = _is_undefined(name)

    if status == "supported":
        assert not undefined, (
            f"{name} is declared supported but this build cannot compile it - "
            "either a dependency narrowed the surface, or the table is wrong"
        )
        return

    if status == "feature:full-stdlib":
        if FULL_STDLIB:
            assert not undefined, (
                f"{name} should be available in a full-stdlib build ({reason})"
            )
        else:
            assert undefined, (
                f"{name} compiles in the default build, but the table says it "
                f"needs full-stdlib ({reason}). The sandbox has been widened "
                "without the table being updated."
            )
        return

    assert undefined, (
        f"{name} is declared unsupported ({reason}) but now compiles - "
        "implement it properly and move it to supported, or fix the table"
    )


def test_sandboxed_build_blocks_host_and_network_access():
    """The posture the README sells, asserted rather than assumed."""
    if FULL_STDLIB:
        pytest.skip("full-stdlib build deliberately enables these")
    for name in ("get_env_var", "get_hostname", "http_request", "dns_lookup"):
        assert _is_undefined(name), f"{name} must not be reachable from caller VRL"
