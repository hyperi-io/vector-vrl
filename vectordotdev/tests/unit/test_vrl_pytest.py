"""VRL expression checks against the real VRL compiler.

Every assertion goes through `validate_vrl` from the compiled bindings,
so a failure means real VRL disagrees. There is no stand-in checker and
no `import vector` fallback: no such top-level package ships, so a
fallback is a guarantee of testing nothing (issue #17).

`validate_vrl` compiles without running, which is exactly the question
these cases ask - does this expression compile - so nothing here needs an
event to run against.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Skip just this module (not the session) when the crate isn't built.
pytest.importorskip(
    "vectordotdev._bindings",
    reason="compiled PyO3 bindings not built - run: cd vector-bindings && maturin develop --release",
)

from vectordotdev import validate_vrl  # noqa: E402


def assert_compiles(expr: str) -> None:
    result = validate_vrl(expr)
    assert result.success is True, f"{expr!r} should compile, got: {result.error}"
    assert result.error is None
    assert result.error_type is None


def assert_rejected(expr: str) -> None:
    result = validate_vrl(expr)
    assert result.success is False, f"{expr!r} should be rejected, but it compiled"
    assert result.error
    assert result.error_type == "compilation_error"


class TestVRLBasics:
    """Expressions the compiler accepts."""

    @pytest.mark.parametrize(
        "expr",
        [
            ". = .message",
            '.level = "INFO"',
            ".processed = true",
            ".enriched = false",
        ],
    )
    def test_valid_field_assignments(self, expr):
        assert_compiles(expr)

    @pytest.mark.parametrize(
        "expr",
        [
            "now()",
            "uuid_v4()",
            "del(.field)",
            "del(.password)",
        ],
    )
    def test_function_calls(self, expr):
        assert_compiles(expr)

    @pytest.mark.parametrize(
        "expr",
        [
            "parse_json!(.message)",
            ".parsed = parse_json(.message) ?? {}",
        ],
    )
    def test_json_parsing(self, expr):
        assert_compiles(expr)

    @pytest.mark.parametrize(
        "expr",
        [
            'if .level == "ERROR" { .alert = true }',
            '.status = if .code == 200 { "ok" } else { "error" }',
        ],
    )
    def test_conditionals(self, expr):
        assert_compiles(expr)


# One call per function, written the way the stdlib actually types it -
# `!` where the function is fallible, real argument types where it is
# picky. A function that has been removed from the stdlib stops
# compiling, which is the point.
STDLIB_CALLS = {
    "now": ".x = now()",
    "uuid_v4": ".x = uuid_v4()",
    "del": ".x = del(.a)",
    "parse_json": ".x = parse_json!(.message)",
    "parse_timestamp": '.x = parse_timestamp!(.s, "%F")',
    "parse_int": ".x = parse_int!(.s)",
    "upcase": ".x = upcase!(.s)",
    "downcase": ".x = downcase!(.s)",
    "strip_whitespace": ".x = strip_whitespace!(.s)",
    "replace": '.x = replace!(.s, "a", "b")',
    "split": '.x = split!(.s, ",")',
    "join": '.x = join!(.arr, ",")',
    "pop": ".x = pop!(.arr)",
    "get": '.x = get!(.obj, ["a"])',
    "length": ".x = length!(.s)",
    "contains": '.x = contains!(.s, "x")',
    "format_timestamp": '.x = format_timestamp!(now(), "%F")',
    "to_string": ".x = to_string!(.n)",
    "to_int": ".x = to_int!(.n)",
    "is_string": ".x = is_string(.s)",
    "is_integer": ".x = is_integer(.s)",
    "is_array": ".x = is_array(.s)",
    "is_object": ".x = is_object(.s)",
}


class TestVRLFunctions:
    """The stdlib functions callers rely on are compiled in."""

    @pytest.mark.parametrize("name", ["now", "uuid_v4", "del"])
    def test_core_functions_available(self, name):
        assert_compiles(STDLIB_CALLS[name])

    @pytest.mark.parametrize("name", ["parse_json", "parse_timestamp", "parse_int"])
    def test_parsing_functions_available(self, name):
        assert_compiles(STDLIB_CALLS[name])

    @pytest.mark.parametrize("name", ["upcase", "downcase", "strip_whitespace", "replace"])
    def test_string_functions_available(self, name):
        assert_compiles(STDLIB_CALLS[name])

    @pytest.mark.parametrize("name", sorted(STDLIB_CALLS))
    def test_documented_stdlib_call_compiles(self, name):
        assert_compiles(STDLIB_CALLS[name])

    def test_undefined_function_is_not_quietly_accepted(self):
        """Positive control for the whole group above.

        Without this, every availability assertion would still pass if
        the compiler stopped resolving function names at all.
        """
        assert_rejected(".x = definitely_not_a_vrl_function!(.s)")


class TestVRLInvalidExpressions:
    """Expressions the compiler rejects."""

    @pytest.mark.parametrize(
        "expr",
        [
            "invalid syntax",
            "parse_nonexistent(.field)",
            ".bad = unknown_func(.data)",
            "if .condition {",
        ],
    )
    def test_syntax_errors_detected(self, expr):
        assert_rejected(expr)

    @pytest.mark.parametrize(
        "expr",
        [
            ". = .field +",
            ".field =",
        ],
    )
    def test_incomplete_expressions_detected(self, expr):
        """A truncated expression is a parse failure, not a lenient pass."""
        assert_rejected(expr)

    def test_empty_source_compiles(self):
        """Empty VRL is a no-op program, not an error."""
        assert_compiles("")


class TestVRLErrorReporting:
    """The failure a caller is handed is usable, not just falsy."""

    def test_undefined_function_names_the_problem(self):
        result = validate_vrl("parse_nonexistent(.field)")
        assert "undefined function" in result.error

    def test_success_carries_no_error(self):
        result = validate_vrl('.level = "INFO"')
        assert result.output == "VRL syntax valid"
        assert result.error is None


def test_yaml_config_validation():
    """The VRL inside a Vector transform config compiles as a whole."""
    import yaml

    config_yaml = """
    sources:
      app:
        type: stdin

    transforms:
      process:
        type: remap
        inputs: ["app"]
        source: |
          .timestamp = now()
          .id = uuid_v4()
          .processed = true

          if .level == "ERROR" {
            .alert = true
          } else {
            .alert = false
          }

    sinks:
      output:
        type: console
        inputs: ["process"]
    """

    config = yaml.safe_load(config_yaml)
    vrl_source = config["transforms"]["process"]["source"]

    # The whole source, not line by line: an `if` block's lines do not
    # compile on their own, so checking them individually measures
    # nothing about the transform.
    assert_compiles(vrl_source)
