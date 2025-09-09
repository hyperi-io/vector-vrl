"""
vectordotdev - Complete PyPI package with bundled Vector bindings.

This package includes the compiled vector-bindings extension and provides
a complete, self-contained Vector integration for Python.
"""

import time

# Import from bundled vector-bindings extension
try:
    # Try bundled extension first (included in PyPI wheel)
    from ._bindings import (
        Vector, VectorCliPy, vrl_check, vrl_functions,
        check_config_syntax_py, parse_cli_args_py
    )
    _bindings_source = "bundled"
    _bindings_available = True
    
except ImportError:
    # Fallback to external vector-bindings if available
    try:
        import vector_bindings
        Vector = vector_bindings.Vector
        VectorCliPy = vector_bindings.VectorCliPy
        vrl_check = vector_bindings.vrl_check
        vrl_functions = vector_bindings.vrl_functions
        check_config_syntax_py = vector_bindings.check_config_syntax_py
        parse_cli_args_py = vector_bindings.parse_cli_args_py
        
        _bindings_source = "external"
        _bindings_available = True
        
    except ImportError as e:
        # No bindings available
        print(f"⚠️ Warning: vector bindings not available: {e}")
        _bindings_available = False
        _bindings_source = "none"
        
        # Stub implementations
        class Vector:
            def __init__(self, config): raise ImportError("Vector bindings not available")
        class VectorCliPy:
            def __init__(self, args): raise ImportError("Vector CLI bindings not available")
        def vrl_check(code): raise ImportError("VRL functions not available")
        def vrl_functions(): raise ImportError("VRL functions not available") 
        def check_config_syntax_py(config): raise ImportError("Config validation not available")
        def parse_cli_args_py(args): raise ImportError("CLI parsing not available")


# Version information
__version__ = "1.0.1"
__author__ = "vectordotdev"


def get_bindings_info():
    """Get information about available bindings"""
    return {
        "available": _bindings_available,
        "source": _bindings_source,
        "version": __version__,
        "bundled": _bindings_source == "bundled"
    }


# Import THG performance assessment
try:
    from .thg_performance import (
        THGPerformanceAssessor, THGMetrics, THGResult,
        quick_thg_assessment, assess_vrl_performance, execute_vector_pipeline
    )
    from .vector_test_utils import VectorTestRunner
    _performance_available = True
except ImportError:
    _performance_available = False
    
    # Fallback functions if performance module unavailable
    def quick_thg_assessment(*args, **kwargs):
        raise ImportError("THG performance assessment not available")
    def assess_vrl_performance(*args, **kwargs):
        raise ImportError("VRL performance assessment not available")
    def execute_vector_pipeline(*args, **kwargs):
        raise ImportError("Vector pipeline execution not available")


# Re-export key components
__all__ = [
    "Vector",
    "VectorCliPy", 
    "vrl_check",
    "vrl_functions", 
    "check_config_syntax_py",
    "parse_cli_args_py",
    "get_bindings_info",
    # THG Performance Assessment
    "THGPerformanceAssessor",
    "THGMetrics", 
    "THGResult",
    "quick_thg_assessment",
    "assess_vrl_performance",
    "execute_vector_pipeline",
    "VectorTestRunner"
]


def assess_vrl_performance(vrl_code: str, test_logs: list, pattern_name: str = "custom") -> dict:
    """
    Assess VRL performance with THG scoring
    
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
        "processing_time_seconds": result.metrics.processing_time_seconds
    }


def execute_vector_pipeline(config: dict, input_data: list, timeout: int = 30) -> dict:
    """
    Execute a Vector pipeline configuration with performance monitoring
    
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
    if 'transforms' in config and 'vrl' in str(config['transforms']):
        vrl_code = str(config['transforms'])
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
            "grade": "A+" if throughput >= 1000 else "A" if throughput >= 500 else "B" if throughput >= 250 else "C" if throughput >= 100 else "D" if throughput >= 50 else "F",
            "thg_estimated": min(1000, throughput * 0.8 + 100)  # Quick THG estimate
        }
    }