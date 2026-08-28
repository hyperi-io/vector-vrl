"""regex2vrl generates high-performance VRL and avoids banned functions.

Pure unit test of the VRL string regex2vrl produces - no Vector process,
no fixtures. The fixture-driven, real-Vector-execution coverage for
production regex/grok patterns lives in tests/e2e/production_patterns.py;
this file checks a narrower, code-quality invariant of the generator
itself: generated VRL must prefer built-in/high-throughput functions and
never fall back to the banned regex-based ones.
"""

from __future__ import annotations

from vectordotdev.regex2vrl.core import RegexToVRL

BANNED_FUNCTIONS = ("parse_regex(", "parse_regex_all(", "parse_grok(", "parse_groks(", "match(", "to_regex(")

GOOD_FUNCTIONS = (
    "string!(", "split(", "contains(", "starts_with(", "ends_with(",
    "parse_json!(", "parse_key_value!(", "parse_syslog!(",
    "to_int(", "to_float(", "length(", "is_ipv4(",
)


def test_generated_vrl_avoids_banned_regex_functions():
    """None of the banned regex-based VRL functions appear in generated code."""
    converter = RegexToVRL()
    patterns = [
        r"^(?P<json_data>\{.*\})$",
        r"(?P<pairs>key1=value1.*key2=value2)",
        r"^(?P<field1>[^|]+)\|(?P<field2>[^|]+)\|(?P<field3>.*)$",
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z) (?P<level>[A-Z]+) (?P<service>\w+) (?P<message>.*)$",
    ]

    for pattern in patterns:
        vrl_code = converter.convert(pattern, output_format="commented")
        found = [fn for fn in BANNED_FUNCTIONS if fn in vrl_code]
        assert not found, f"pattern {pattern!r} generated banned function(s) {found}:\n{vrl_code}"


def test_generated_vrl_uses_high_performance_functions():
    """Generated VRL uses at least one of the known high-throughput functions."""
    converter = RegexToVRL()
    vrl_code = converter.convert(r"^(?P<json_data>\{.*\})$", output_format="commented")

    assert any(fn in vrl_code for fn in GOOD_FUNCTIONS), (
        f"expected at least one high-performance function in generated VRL:\n{vrl_code}"
    )
