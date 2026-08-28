"""Mandatory startup smoke test - catches import-time crashes and broken wiring."""

from __future__ import annotations

import importlib


def test_package_imports_without_crashing() -> None:
    """The package must import cleanly, with or without compiled bindings."""
    module = importlib.import_module("vectordotdev")
    assert module is not None


def test_bindings_info_reports_a_source() -> None:
    """get_bindings_info() must report a real source, never crash."""
    import vectordotdev

    info = vectordotdev.get_bindings_info()
    assert info["source"] in ("bundled", "external", "none")


def test_regex2vrl_core_imports() -> None:
    """regex2vrl is standalone - it must import with zero Rust bindings."""
    module = importlib.import_module("vectordotdev.regex2vrl.core")
    assert module is not None
