"""Run VRL's own upstream examples through this engine.

Every stdlib function ships `examples()` - runnable VRL WITH its expected
result, authored by the people who wrote the function. That is a far better
conformance corpus than anything written here would be, and it refreshes when
vrl does. tests/data/vrl_examples.json is a dump of it; regenerate with
build/vrl-examples-probe.

This complements test_function_coverage.py rather than repeating it: that one
proves each function EXISTS, this one proves it BEHAVES.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vector_vrl import execute_vrl, validate_vrl

DATA = Path(__file__).parent.parent / "data"
EXAMPLES = json.loads((DATA / "vrl_examples.json").read_text(encoding="utf-8"))

# Value-comparable matches on the sandboxed build at the time of writing.
# Asserted as a floor so the value checking cannot silently decay into a
# compile-only smoke test, which is the failure mode this corpus exists to
# prevent.
VALUE_MATCH_FLOOR = 481


# Examples upstream did not flag `skip` but which read a file that only exists
# in vrl's own repo. Vector 0.58.0 rejects this one identically - same E403,
# "Unable to open alias source file" - so excluding it costs no coverage.
NEEDS_UPSTREAM_FILES = ("alias_sources:",)


def _needs_upstream_files(example: dict) -> bool:
    return any(marker in example["source"] for marker in NEEDS_UPSTREAM_FILES)


def _gated() -> set[str]:
    """Functions the default build does not compile, per the coverage table."""
    out = set()
    for line in (
        (DATA / "vector_vrl_functions.tsv").read_text(encoding="utf-8").splitlines()
    ):
        if line.startswith("#") or not line.strip():
            continue
        name, status, *_ = line.split("\t")
        if status != "supported":
            out.add(name)
    return out


GATED = _gated()
RUNNABLE = [e for e in EXAMPLES if not e["skip"] and not _needs_upstream_files(e)]


def _normalise(value):
    """Compare structurally - nested values come back as JSON strings."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _seed(example: dict) -> str:
    return example["input"] or '{"__seed": 1}'


def _run(example: dict) -> tuple[str, object]:
    """Run one example. Returns (outcome, value).

    Wrapping the source in an assignment is what makes its return value
    readable, since execute_vrl hands back the mutated event rather than the
    program's own result. Multi-statement examples cannot be wrapped, so they
    run bare and are checked for execution only.
    """
    source = example["source"]
    wrapped = f".__result = {source}"

    if validate_vrl(wrapped).success:
        events = execute_vrl(wrapped, [_seed(example)])
        out = events[0]
        if "error" in out and "__result" not in out:
            return "error", out["error"]
        return "value", out.get("__result")

    if not validate_vrl(source).success:
        return "compile_fail", validate_vrl(source).error

    out = execute_vrl(source, [_seed(example)])[0]
    if "error" in out:
        return "error", out["error"]
    return "ran", out


@pytest.mark.parametrize(
    "example",
    RUNNABLE,
    ids=[f"{e['function']}-{i}" for i, e in enumerate(RUNNABLE)],
)
def test_upstream_example(example: dict):
    outcome, value = _run(example)

    if example["function"] in GATED:
        assert outcome == "compile_fail", (
            f"{example['function']} is not in the default build, so its example "
            "should not compile"
        )
        return

    if example["err"] is not None:
        assert outcome in ("error", "compile_fail"), (
            f"upstream expects this to fail: {example['err']}"
        )
        return

    assert outcome != "compile_fail", f"upstream example does not compile: {value}"
    assert outcome != "error", f"upstream example errored at runtime: {value}"


def test_value_assertions_have_not_decayed():
    """Most examples are checked on VALUE, and that must not quietly stop."""
    matched = 0
    for example in RUNNABLE:
        if example["function"] in GATED or example["err"] is not None:
            continue
        outcome, value = _run(example)
        if outcome != "value":
            continue
        if (
            _normalise(value) == _normalise(example["ok"])
            or str(value) == example["ok"]
        ):
            matched += 1

    assert matched >= VALUE_MATCH_FLOOR, (
        f"only {matched} examples matched their upstream expected value, "
        f"down from {VALUE_MATCH_FLOOR} - behaviour has changed, or the "
        "comparison has broken"
    )


def test_the_corpus_is_present_and_broad():
    """A truncated corpus would make every test above vacuous."""
    assert len(EXAMPLES) > 600, f"corpus looks truncated: {len(EXAMPLES)} examples"
    assert len({e["function"] for e in EXAMPLES}) > 195
