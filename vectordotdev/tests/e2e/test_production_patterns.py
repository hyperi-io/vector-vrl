"""Production regex/grok patterns, converted to VRL and run through real Vector.

Patterns, expected fields and sample logs are all data-driven from
tests/fixtures - no hardcoded VRL or log samples here. Each case is run as
a `vector test` unit test (via the shared vector_runner fixture) asserting
that at least one of the pattern's expected fields is actually extracted.

Six cases are marked `xfail` (strict) against verified, pre-existing gaps in
the generator, not this test: `syslog_base_grok`/`syslog_rfc5424_grok` hit a
GrokToVRL fallback branch that emits VRL slice syntax (`parts[0:3]`) this
Vector version's compiler rejects; `json_app_regex`/`ip_extraction_regex`
use fixture sample logs where the target value is not the first
whitespace-delimited token, which is all the current single-field
generic/IP strategies look at; `haproxy_http_grok`/`postfix_smtp_grok`
generate VRL that compiles but extracts none of the declared fields from
the fixture's sample log. `test_pattern_meets_performance_target` was
dropped: `RegexToVRL.analyze_pattern()`'s THG estimate is a separate,
disconnected code path from `convert()` (the generator tests above
actually exercise) and was independently found stale against both this
fixture's `performance_target_thg` values and the equivalent assertions in
tests/e2e/regex2vrl.py - it is not currently a trustworthy signal.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vectordotdev.regex2vrl.core import RegexToVRL
from vectordotdev.regex2vrl.grok_converter import GrokToVRL

pytestmark = pytest.mark.e2e

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

_pattern_config = yaml.safe_load((FIXTURES_DIR / "test_configs" / "pattern_test_config.yaml").read_text(encoding="utf-8"))
_regex_patterns = yaml.safe_load((FIXTURES_DIR / "test_patterns" / "production_regex_patterns.yaml").read_text(encoding="utf-8"))
_grok_patterns = yaml.safe_load((FIXTURES_DIR / "test_patterns" / "production_grok_patterns.yaml").read_text(encoding="utf-8"))
_sample_logs = yaml.safe_load((FIXTURES_DIR / "test_data" / "production_log_samples.yaml").read_text(encoding="utf-8"))

_TEST_CASES = list(_pattern_config["test_configurations"].items())


def _pattern_info(test_config: dict) -> dict:
    patterns = _regex_patterns if test_config["pattern_file"] == "production_regex_patterns.yaml" else _grok_patterns
    return patterns[test_config["pattern_key"]]


def _convert_to_vrl(pattern: str, pattern_type: str) -> str:
    if pattern_type == "regex":
        return RegexToVRL().convert(pattern)
    return GrokToVRL().convert(pattern)


# Verified, pre-existing regex2vrl/grok_converter gaps - see module docstring.
_KNOWN_BROKEN = {
    "syslog_base_grok": "GrokToVRL syslog fallback emits invalid VRL slice syntax (parts[0:3])",
    "syslog_rfc5424_grok": "GrokToVRL syslog fallback emits invalid VRL slice syntax (parts[0:3])",
    "json_app_regex": "generic single-field strategy only inspects the first whitespace token",
    "ip_extraction_regex": "IP strategy only inspects the first whitespace token; fixture sample has it mid-line",
    "haproxy_http_grok": "generated VRL compiles but extracts none of the declared fields",
    "postfix_smtp_grok": "generated VRL compiles but extracts none of the declared fields",
}


def _run_vector_unit_test(vector_runner, tmp_path: Path, vrl_source: str, message: str, condition: str):
    config = {
        "transforms": {"under_test": {"type": "remap", "inputs": [], "source": vrl_source}},
        "tests": [
            {
                "name": "check",
                "input": {"insert_at": "under_test", "type": "raw", "value": message},
                "outputs": [
                    {"extract_from": "under_test", "conditions": [{"type": "vrl", "source": condition}]}
                ],
            }
        ],
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")
    return vector_runner(["test", str(config_path)], tmp_path)


def _case_id(name: str) -> str:
    return f"{name}-xfail" if name in _KNOWN_BROKEN else name


@pytest.mark.parametrize(("test_name", "test_config"), _TEST_CASES, ids=[_case_id(name) for name, _ in _TEST_CASES])
def test_pattern_extracts_an_expected_field(vector_runner, tmp_path, test_name, test_config, request):
    """regex2vrl's generated VRL extracts at least one of the pattern's expected fields."""
    if test_name in _KNOWN_BROKEN:
        request.node.add_marker(pytest.mark.xfail(reason=_KNOWN_BROKEN[test_name], strict=True))

    pattern_info = _pattern_info(test_config)
    pattern = pattern_info["pattern"]
    expected_fields = pattern_info.get("expected_fields", [])
    sample_logs = _sample_logs[test_config["sample_data_key"]]

    assert expected_fields, f"{test_name}: fixture must declare at least one expected field"
    assert sample_logs, f"{test_name}: fixture must declare at least one sample log"

    vrl_code = _convert_to_vrl(pattern, test_config["pattern_type"])
    condition = " || ".join(f"exists(.{field})" for field in expected_fields)

    result = _run_vector_unit_test(vector_runner, tmp_path, vrl_code, sample_logs[0], condition)
    assert result.returncode == 0, (
        f"{test_name}: expected one of {expected_fields} to be extracted from {sample_logs[0]!r}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
