"""validate_config against the real VRL compiler - no mocks, no fake results.

Every "this VRL is broken" case here is broken according to the actual
compiler, not according to a fixture that asserts what we hoped it would say.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vector_vrl import validate_config

GOOD_VRL = ".level = upcase!(.level)"
# Missing the required `!` on a fallible call - genuinely uncompilable.
BAD_VRL = ".parsed = parse_json(.message)\n.x = upcase(.parsed)"


def _remap(source: str) -> dict:
    return {"type": "remap", "inputs": ["in"], "source": source}


class TestInlineSource:
    """Configs handed over as an already-parsed dict."""

    def test_a_compiling_remap_passes(self):
        result = validate_config({"transforms": {"t": _remap(GOOD_VRL)}})
        assert result.ok
        assert [c.name for c in result.checked] == ["t"]
        assert result.failures == ()

    def test_a_broken_remap_fails_and_names_the_transform(self):
        result = validate_config({"transforms": {"bad": _remap(BAD_VRL)}})
        assert not result.ok
        assert [f.name for f in result.failures] == ["bad"]
        assert result.failures[0].error

    def test_one_bad_transform_among_several_is_isolated(self):
        result = validate_config(
            {
                "transforms": {
                    "a": _remap(GOOD_VRL),
                    "b": _remap(BAD_VRL),
                    "c": _remap(GOOD_VRL),
                }
            }
        )
        assert not result.ok
        assert [f.name for f in result.failures] == ["b"]
        assert len(result.checked) == 3

    def test_non_remap_transforms_are_not_checked(self):
        result = validate_config(
            {"transforms": {"f": {"type": "filter", "condition": ".x == 1"}}}
        )
        assert result.ok
        assert result.checked == ()

    def test_remap_reading_vrl_from_a_file_is_skipped_not_guessed(self):
        result = validate_config(
            {"transforms": {"ext": {"type": "remap", "file": "t.vrl"}}}
        )
        assert result.ok
        assert result.skipped == ("ext",)
        assert result.checked == ()

    def test_a_config_with_no_transforms_is_vacuously_ok(self):
        assert validate_config({"sources": {"in": {"type": "stdin"}}}).ok

    def test_transforms_not_a_mapping_is_an_error(self):
        with pytest.raises(ValueError, match="not a mapping"):
            validate_config({"transforms": ["nope"]})


class TestFileFormats:
    """TOML and JSON parse with the stdlib - no extra required."""

    def test_toml_config(self, tmp_path: Path):
        cfg = tmp_path / "vector.toml"
        cfg.write_text(
            f"[transforms.t]\ntype = \"remap\"\nsource = '''\n{GOOD_VRL}\n'''\n",
            encoding="utf-8",
        )
        assert validate_config(cfg).ok

    def test_json_config_reports_a_real_failure(self, tmp_path: Path):
        cfg = tmp_path / "vector.json"
        cfg.write_text(
            json.dumps({"transforms": {"t": _remap(BAD_VRL)}}), encoding="utf-8"
        )
        result = validate_config(cfg)
        assert not result.ok
        assert result.failures[0].name == "t"

    def test_a_path_given_as_a_string_works(self, tmp_path: Path):
        cfg = tmp_path / "vector.json"
        cfg.write_text(
            json.dumps({"transforms": {"t": _remap(GOOD_VRL)}}), encoding="utf-8"
        )
        assert validate_config(str(cfg)).ok

    def test_yaml_config(self, tmp_path: Path):
        pytest.importorskip("yaml", reason="needs the vector-vrl[yaml] extra")
        cfg = tmp_path / "vector.yaml"
        cfg.write_text(
            "transforms:\n"
            "  t:\n"
            "    type: remap\n"
            "    inputs: [in]\n"
            f"    source: '{GOOD_VRL}'\n",
            encoding="utf-8",
        )
        assert validate_config(cfg).ok

    def test_an_unsupported_suffix_is_rejected(self, tmp_path: Path):
        cfg = tmp_path / "vector.ini"
        cfg.write_text("nope", encoding="utf-8")
        with pytest.raises(ValueError, match="unsupported Vector config format"):
            validate_config(cfg)

    def test_a_file_that_is_not_a_mapping_is_rejected(self, tmp_path: Path):
        cfg = tmp_path / "vector.json"
        cfg.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="did not parse to a mapping"):
            validate_config(cfg)


class TestFunctionsThisBuildCannotCompile:
    """A valid config must never be reported as broken.

    Enrichment tables and secret backends are declared in the Vector config
    outside VRL, and Vector registers those functions only once it has loaded
    that config. The env/network functions are left out deliberately. VRL
    calling either is unchecked here, never a failure.
    """

    ENRICHMENT = '. = get_enrichment_table_record!("geoip", {"ip": .ip})'
    SANDBOXED = ".h = get_hostname!()"

    @pytest.mark.parametrize(
        "vrl", [ENRICHMENT, SANDBOXED], ids=["enrichment", "sandbox"]
    )
    def test_is_unchecked_not_failed(self, vrl: str):
        result = validate_config({"transforms": {"t": _remap(vrl)}})
        assert result.ok, "a config this build cannot check is not a broken config"
        assert result.failures == ()
        assert [u.name for u in result.unchecked] == ["t"]
        assert result.checked[0].error is None

    def test_secrets_vrl_is_genuinely_checked_now(self):
        """The secret functions are compiled in, so a config using them is judged.

        This was unchecked until the three were implemented; if it ever goes
        back to unchecked, something dropped them from the build.
        """
        result = validate_config(
            {"transforms": {"t": _remap('.k = get_secret("datadog_api_key")')}}
        )
        assert result.ok
        assert result.unchecked == ()

    def test_the_reason_names_the_offending_function(self):
        result = validate_config({"transforms": {"t": _remap(self.ENRICHMENT)}})
        assert "get_enrichment_table_record" in result.unchecked[0].unchecked_reason

    def test_a_real_error_still_fails_alongside_an_unchecked_one(self):
        result = validate_config(
            {
                "transforms": {
                    "enriched": _remap(self.ENRICHMENT),
                    "broken": _remap(BAD_VRL),
                }
            }
        )
        assert not result.ok
        assert [f.name for f in result.failures] == ["broken"]
        assert [u.name for u in result.unchecked] == ["enriched"]
