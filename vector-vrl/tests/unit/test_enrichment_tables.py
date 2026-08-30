"""Enrichment tables, exercised against real CSV files and the real VRL engine.

The registry is process-global, so every test clears it first and the module
never assumes what ran before it.
"""

from pathlib import Path

import pytest

from vector_vrl import (
    clear_enrichment_tables,
    execute_vrl,
    list_enrichment_tables,
    register_enrichment_table,
    validate_vrl,
)

USERS = "id,name,team\n1,Bob,red\n2,Fred,blue\n3,Alice,red\n"
SEED = ['{"message":"seed"}']

GET = '. = get_enrichment_table_record!("users", {"id":"2"})'
FIND = '. = {"rows": find_enrichment_table_records!("users", {"team":"red"})}'


@pytest.fixture
def users_csv(tmp_path: Path) -> Path:
    path = tmp_path / "users.csv"
    path.write_text(USERS, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_enrichment_tables()
    yield
    clear_enrichment_tables()


def test_an_unregistered_table_is_a_compile_error():
    result = validate_vrl(GET)
    assert not result.success
    assert "unknown enrichment table" in result.error


def test_registering_makes_the_program_compile(users_csv: Path):
    register_enrichment_table("users", "file", str(users_csv))
    assert validate_vrl(GET).success


def test_the_diagnostic_names_the_registered_tables(users_csv: Path):
    register_enrichment_table("users", "file", str(users_csv))
    result = validate_vrl('. = get_enrichment_table_record!("usres", {"id":"1"})')
    assert not result.success
    assert "usres" in result.error
    assert "users" in result.error


def test_get_returns_the_row(users_csv: Path):
    register_enrichment_table("users", "file", str(users_csv))
    out = execute_vrl(GET, SEED)[0]
    assert out["name"] == "Fred"
    assert out["team"] == "blue"


def test_get_errors_on_a_miss(users_csv: Path):
    register_enrichment_table("users", "file", str(users_csv))
    out = execute_vrl('. = get_enrichment_table_record!("users", {"id":"99"})', SEED)[0]
    assert "No rows found" in out["error"]


def test_get_errors_when_several_rows_match(users_csv: Path):
    register_enrichment_table("users", "file", str(users_csv))
    out = execute_vrl(
        '. = get_enrichment_table_record!("users", {"team":"red"})', SEED
    )[0]
    assert "More than one row found" in out["error"]


def test_find_returns_every_match(users_csv: Path):
    register_enrichment_table("users", "file", str(users_csv))
    out = execute_vrl(FIND, SEED)[0]
    # Nested values come back as JSON text, as the Python API reference documents.
    assert out["rows"].count('"name"') == 2
    assert "Bob" in out["rows"]
    assert "Alice" in out["rows"]


def test_a_tsv_loads_with_an_explicit_delimiter(tmp_path: Path):
    path = tmp_path / "users.tsv"
    path.write_text(USERS.replace(",", "\t"), encoding="utf-8")
    register_enrichment_table("users", "file", str(path), delimiter="\t")
    assert execute_vrl(GET, SEED)[0]["name"] == "Fred"


def test_listing_reports_the_registered_tables(users_csv: Path):
    assert list_enrichment_tables() == []
    register_enrichment_table("users", "file", str(users_csv))
    listed = list_enrichment_tables()
    assert listed == [
        {"name": "users", "kind": "file", "path": str(users_csv), "rows": 3}
    ]
    clear_enrichment_tables()
    assert list_enrichment_tables() == []


def test_a_missing_file_is_rejected_at_registration(tmp_path: Path):
    with pytest.raises(ValueError, match="cannot read csv"):
        register_enrichment_table("users", "file", str(tmp_path / "nope.csv"))


def test_an_unknown_kind_is_rejected(users_csv: Path):
    with pytest.raises(ValueError, match="unknown enrichment table kind"):
        register_enrichment_table("users", "sqlite", str(users_csv))


def test_a_multi_character_delimiter_is_rejected(users_csv: Path):
    with pytest.raises(ValueError, match="single ASCII character"):
        register_enrichment_table("users", "file", str(users_csv), delimiter="||")


def test_vrl_cannot_name_a_path_as_a_table(users_csv: Path):
    # The table argument must be a literal the registry knows, so VRL can never
    # point the reader at a file of its own choosing.
    register_enrichment_table("users", "file", str(users_csv))
    result = validate_vrl(
        f'. = get_enrichment_table_record!("{users_csv}", {{"id":"1"}})'
    )
    assert not result.success


def test_sandboxed_functions_stay_unavailable():
    # Enrichment must not have widened what caller-supplied VRL can reach.
    for call in [
        '.x = get_env_var!("HOME")',
        ".x = get_hostname!()",
        '.x = http_request!("http://169.254.169.254/")',
        '.x = dns_lookup!("example.com")',
    ]:
        assert not validate_vrl(call).success, call
