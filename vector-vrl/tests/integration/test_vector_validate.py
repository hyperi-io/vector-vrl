"""validate_config_with_vector against a real `vector` binary.

The point of this surface is catching what the in-process check cannot, so the
cases here are deliberately the ones `validate_config` gets wrong on its own:
broken wiring between components, and VRL whose enrichment table is declared
in the config rather than in the VRL.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from vector_vrl import validate_config, validate_config_with_vector

pytestmark = pytest.mark.integration

GOOD = """
sources:
  in:
    type: stdin
transforms:
  t:
    type: remap
    inputs: [in]
    source: '.level = upcase!(.level)'
sinks:
  out:
    type: console
    inputs: [t]
    encoding:
      codec: json
"""

# The VRL compiles fine; the transform reads from a component that is not
# there. Nothing in-process can see this.
BAD_WIRING = GOOD.replace("inputs: [in]", "inputs: [does_not_exist]")

ENRICHMENT = """
enrichment_tables:
  users:
    type: file
    file:
      path: users.csv
      encoding:
        type: csv
    schema:
      id: string
      name: string
sources:
  in:
    type: stdin
transforms:
  enrich:
    type: remap
    inputs: [in]
    source: |
      row = get_enrichment_table_record!("users", {"id": .id})
      .name = row.name
sinks:
  out:
    type: console
    inputs: [enrich]
    encoding:
      codec: json
"""


def _require_vector() -> None:
    if shutil.which("vector"):
        return
    if os.environ.get("CI"):
        pytest.fail(
            "no vector binary in CI - the test image is missing it, which is "
            "an environment gap rather than a real skip"
        )
    pytest.skip("no vector binary on PATH")


def _write(tmp_path: Path, body: str) -> Path:
    cfg = tmp_path / "vector.yaml"
    cfg.write_text(body, encoding="utf-8")
    return cfg


def test_a_good_config_validates(tmp_path: Path):
    _require_vector()
    result = validate_config_with_vector(_write(tmp_path, GOOD))
    assert result.ok, result.output
    assert result.returncode == 0


def test_broken_wiring_is_caught_and_named(tmp_path: Path):
    _require_vector()
    cfg = _write(tmp_path, BAD_WIRING)

    # The in-process check passes it - the VRL itself is valid.
    assert validate_config(cfg).ok

    result = validate_config_with_vector(cfg)
    assert not result.ok
    assert result.returncode != 0
    assert "does_not_exist" in result.output


def test_enrichment_vrl_validates_through_the_binary(tmp_path: Path):
    _require_vector()
    (tmp_path / "users.csv").write_text("id,name\n1,alice\n", encoding="utf-8")
    cfg = _write(tmp_path, ENRICHMENT)

    # In-process this cannot be judged - Vector registers the enrichment
    # functions from the config, so the compiler here has never heard of them.
    in_process = validate_config(cfg)
    assert in_process.ok
    assert [u.name for u in in_process.unchecked] == ["enrich"]

    result = validate_config_with_vector(cfg)
    assert result.ok, result.output


def test_a_missing_binary_says_what_to_do(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="validate_config"):
        validate_config_with_vector(
            _write(tmp_path, GOOD), vector_binary="vector-not-installed"
        )
