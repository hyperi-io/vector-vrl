"""vector-vrl - run Vector's transform language (VRL) in Python, in-process.

Wraps the compiled `vector-bindings` extension, which links Vector's own VRL
compiler and runtime. This is the VRL language only - there is no
sources/transforms/sinks pipeline here.
"""

import time
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from .config_check import (
    ConfigCheck,
    TransformCheck,
    VectorValidation,
    validate_config,
    validate_config_with_vector,
)

# Import from bundled vector-bindings extension
try:
    # Try bundled extension first (included in PyPI wheel)
    from ._bindings import (
        Vector,
        VrlResult,
        clear_enrichment_tables,
        execute_vrl,
        get_vrl_performance,
        list_enrichment_tables,
        register_enrichment_table,
        validate_vrl,
    )

    _bindings_source = "bundled"
    _bindings_available = True

except ImportError:  # pragma: no cover - only reachable if the wheel shipped without its compiled extension
    # Fallback to external vector-bindings if available
    try:
        import vector_bindings

        Vector = vector_bindings.Vector
        VrlResult = vector_bindings.VrlResult
        execute_vrl = vector_bindings.execute_vrl
        validate_vrl = vector_bindings.validate_vrl
        get_vrl_performance = vector_bindings.get_vrl_performance
        register_enrichment_table = vector_bindings.register_enrichment_table
        clear_enrichment_tables = vector_bindings.clear_enrichment_tables
        list_enrichment_tables = vector_bindings.list_enrichment_tables

        _bindings_source = "external"
        _bindings_available = True

    except ImportError as e:
        # No bindings available
        print(f"Warning: vector bindings not available: {e}")
        _bindings_available = False
        _bindings_source = "none"

        # Stub implementations
        class Vector:
            """Placeholder Vector used when the native bindings are unavailable."""

            def __init__(self, config):
                """Raise ImportError because Vector bindings are not available."""
                raise ImportError("Vector bindings not available")

        class VrlResult:
            """Placeholder VrlResult used when the native bindings are unavailable."""

            def __init__(self, *args, **kwargs):
                """Raise ImportError because VRL bindings are not available."""
                raise ImportError("VRL bindings not available")

        def execute_vrl(code, data):
            """Raise ImportError because VRL bindings are not available."""
            raise ImportError("VRL bindings not available")

        def validate_vrl(code):
            """Raise ImportError because VRL bindings are not available."""
            raise ImportError("VRL bindings not available")

        def get_vrl_performance(code, data, iterations=None):
            """Raise ImportError because VRL bindings are not available."""
            raise ImportError("VRL bindings not available")

        def register_enrichment_table(name, kind, path, delimiter=None):
            """Raise ImportError because VRL bindings are not available."""
            raise ImportError("VRL bindings not available")

        def clear_enrichment_tables():
            """Raise ImportError because VRL bindings are not available."""
            raise ImportError("VRL bindings not available")

        def list_enrichment_tables():
            """Raise ImportError because VRL bindings are not available."""
            raise ImportError("VRL bindings not available")


# Version information - read from the installed package's own metadata
# (stamped into pyproject.toml at release time by hyperi-ci stamp-version),
# never hardcoded here as a second value that could drift from it.
try:
    __version__ = _pkg_version("vector-vrl")
except PackageNotFoundError:  # pragma: no cover - editable/dev install, no metadata
    __version__ = "0.0.0+unknown"
__author__ = "HyperI"


def get_bindings_info():
    """Get information about available bindings."""
    return {
        "available": _bindings_available,
        "source": _bindings_source,
        "version": __version__,
        "bundled": _bindings_source == "bundled",
    }


# Import THG performance assessment and production patterns
try:
    from .production_patterns import (
        ProductionPatterns,
        get_apache_combined,
        get_docker_container,
        get_json_application,
        get_kubernetes_pods,
        get_nginx_access,
        production_patterns,
    )
    from .thg_performance import (
        THGMetrics,
        THGPerformanceAssessor,
        THGResult,
        quick_thg_assessment,
    )
    from .vector_test_utils import VectorTestRunner

    _performance_available = True
except (
    ImportError
):  # pragma: no cover - only reachable if a subprocess-based module fails to import
    _performance_available = False

    # Fallback functions if performance module unavailable
    def quick_thg_assessment(*args, **kwargs):
        """Raise ImportError because THG performance assessment is not available."""
        raise ImportError("THG performance assessment not available")

    def assess_vrl_performance(*args, **kwargs):
        """Raise ImportError because VRL performance assessment is not available."""
        raise ImportError("VRL performance assessment not available")

    def execute_vector_pipeline(*args, **kwargs):
        """Raise ImportError because Vector pipeline execution is not available."""
        raise ImportError("Vector pipeline execution not available")


# Re-export key components
__all__ = [
    "Vector",
    "VrlResult",
    "execute_vrl",
    "validate_vrl",
    "get_vrl_performance",
    "get_bindings_info",
    # Enrichment tables, registered before the VRL that uses them is compiled
    "register_enrichment_table",
    "clear_enrichment_tables",
    "list_enrichment_tables",
    # Vector-config checking
    "validate_config",
    "validate_config_with_vector",
    "ConfigCheck",
    "TransformCheck",
    "VectorValidation",
    # THG Performance Assessment
    "THGPerformanceAssessor",
    "THGMetrics",
    "THGResult",
    "quick_thg_assessment",
    "assess_vrl_performance",
    "execute_vector_pipeline",
    "VectorTestRunner",
    # Production Patterns
    "ProductionPatterns",
    "production_patterns",
    "get_apache_combined",
    "get_nginx_access",
    "get_json_application",
    "get_kubernetes_pods",
    "get_docker_container",
]


def assess_vrl_performance(
    vrl_code: str, test_logs: list, pattern_name: str = "custom"
) -> dict:  # pragma: no cover - delegates to thg_performance.py, outside the tested bindings surface
    """Assess VRL performance with THG scoring.

    Args:
        vrl_code: VRL code to test
        test_logs: List of test log entries
        pattern_name: Name for the pattern being tested

    Returns:
        dict: Complete THG assessment results
    """
    if not _performance_available:
        raise ImportError("THG performance assessment not available")

    assessor = THGPerformanceAssessor()
    result = assessor.assess_pattern_performance(pattern_name, vrl_code, test_logs)

    return {
        "thg_score": result.thg_score,
        "performance_grade": result.performance_grade,
        "events_per_second": result.metrics.events_per_second,
        "bytes_per_second": result.metrics.bytes_per_second,
        "latency_p95_ms": result.metrics.latency_p95,
        "error_rate_percent": result.metrics.error_rate_percent,
        "recommendations": result.recommendations,
        "processing_time_seconds": result.metrics.processing_time_seconds,
    }


def execute_vector_pipeline(
    config: dict, input_data: list, timeout: int = 30
) -> dict:  # pragma: no cover - delegates to vector_test_utils.py, outside the tested bindings surface
    """Execute a Vector pipeline configuration with performance monitoring.

    Args:
        config: Vector configuration dictionary
        input_data: List of input log entries
        timeout: Execution timeout in seconds

    Returns:
        dict: Execution results with performance metrics
    """
    if not _performance_available:
        raise ImportError("Vector pipeline execution not available")

    runner = VectorTestRunner()

    # Convert config to VRL if needed
    if "transforms" in config and "vrl" in str(config["transforms"]):
        vrl_code = str(config["transforms"])
    else:
        vrl_code = "# Configuration-based processing\n."

    start_time = time.time()
    success, results, error_msg = runner.test_vrl_with_vector(vrl_code, input_data)
    end_time = time.time()

    processing_time = end_time - start_time
    events_processed = len(results) if success else 0
    throughput = events_processed / processing_time if processing_time > 0 else 0

    return {
        "success": success,
        "events_processed": events_processed,
        "processing_time_seconds": processing_time,
        "throughput_eps": throughput,
        "results": results if success else [],
        "error_message": error_msg if not success else None,
        "performance_summary": {
            "grade": "A+"
            if throughput >= 1000
            else "A"
            if throughput >= 500
            else "B"
            if throughput >= 250
            else "C"
            if throughput >= 100
            else "D"
            if throughput >= 50
            else "F",
            "thg_estimated": min(1000, throughput * 0.8 + 100),  # Quick THG estimate
        },
    }
