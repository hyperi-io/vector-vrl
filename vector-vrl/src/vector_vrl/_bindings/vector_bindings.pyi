"""Type stub for the compiled `vector_bindings` extension (vector-bindings/src/lib.rs).

Hand-written from the pyo3 signatures: `#[pyfunction]`/`#[pymethods]` in
lib.rs are the source of truth, and `tests/unit/test_bindings_stub.py` checks
this file's names, members and parameter lists against the loaded module.
Types are not visible at runtime, so they are checked by eye against lib.rs.
Sequence arguments are `list | tuple`: that is what pyo3 extracts a `Vec`
from, and a bare `str` or an iterator is rejected.
"""

from typing import Any, TypedDict

__all__ = [
    "Vector",
    "VrlResult",
    "__version__",
    "clear_enrichment_tables",
    "execute_vrl",
    "execute_vrl_with_secrets",
    "get_vrl_performance",
    "list_enrichment_tables",
    "register_enrichment_table",
    "validate_vrl",
]

__version__: str

class _VectorStats(TypedDict):
    events_processed: int
    bytes_processed: int
    errors: int
    uptime_seconds: float

class _PerformanceMetrics(TypedDict):
    events_per_second: float
    processing_time_seconds: float
    total_events: int
    thg_score: float

class _EnrichmentTableInfo(TypedDict):
    name: str
    kind: str
    path: str
    rows: int | None

class _SecretsEntry(TypedDict):
    event: dict[str, Any]
    secrets: dict[str, str]

class VrlResult:
    """Outcome of `validate_vrl`. Read-only; never constructed from Python."""

    @property
    def success(self) -> bool: ...
    @property
    def output(self) -> str | None: ...
    @property
    def error(self) -> str | None: ...
    @property
    def error_type(self) -> str | None: ...
    def __repr__(self) -> str: ...

class Vector:
    """In-process VRL runner with real counters.

    `config_dict` is stored and never applied - there is no pipeline here.
    """

    def __init__(self, config_dict: dict[str, Any]) -> None: ...
    def initialize(self) -> bool:
        """Start the uptime clock and zero the counters."""

    def process_logs(
        self, logs: list[str] | tuple[str, ...], vrl_code: str
    ) -> list[dict[str, Any]]:
        """Run `vrl_code` over each log; raises RuntimeError before `initialize()`."""

    def get_stats(self) -> _VectorStats:
        """Counts since the last `initialize()`."""

def execute_vrl(
    vrl_code: str,
    input_data: list[str] | tuple[str, ...],
    secrets: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """One dict per event: its fields on success, `error` and `original` on failure."""

def execute_vrl_with_secrets(
    vrl_code: str,
    input_data: list[str] | tuple[str, ...],
    secrets: dict[str, str] | None = None,
) -> list[_SecretsEntry]:
    """One entry per event: `event` is what `execute_vrl` returns, `secrets` its final store."""

def validate_vrl(vrl_code: str) -> VrlResult:
    """Compile only; never runs the program."""

def get_vrl_performance(
    vrl_code: str,
    test_data: list[str] | tuple[str, ...],
    iterations: int | None = None,
) -> _PerformanceMetrics:
    """Run `test_data` `iterations` times (default 100); capped at 1M events total."""

def register_enrichment_table(
    name: str,
    kind: str,
    path: str,
    delimiter: str | None = None,
) -> None:
    """Register a `file` (CSV) or `geoip` (mmdb) table before compiling VRL that uses it."""

def clear_enrichment_tables() -> None:
    """Empty the registry; already-compiled programs keep their captured tables."""

def list_enrichment_tables() -> list[_EnrichmentTableInfo]:
    """Registered tables, name-ordered; `rows` is None for a geoip table."""
