"""Mandatory startup smoke test - catches import-time crashes and broken wiring."""

from __future__ import annotations

import importlib


def test_package_imports_without_crashing() -> None:
    """The package must import cleanly, with or without compiled bindings."""
    module = importlib.import_module("vector_vrl")
    assert module is not None


def test_bindings_info_reports_a_source() -> None:
    """get_bindings_info() must report a real source, never crash."""
    import vector_vrl

    info = vector_vrl.get_bindings_info()
    assert info["source"] in ("bundled", "external", "none")
