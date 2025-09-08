"""
vectordotdev - Complete PyPI package with bundled Vector bindings.

This package includes the compiled vector-bindings extension and provides
a complete, self-contained Vector integration for Python.
"""

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
__version__ = "1.0.0"
__author__ = "vectordotdev"


def get_bindings_info():
    """Get information about available bindings"""
    return {
        "available": _bindings_available,
        "source": _bindings_source,
        "version": __version__,
        "bundled": _bindings_source == "bundled"
    }


# Re-export key components
__all__ = [
    "Vector",
    "VectorCliPy", 
    "vrl_check",
    "vrl_functions", 
    "check_config_syntax_py",
    "parse_cli_args_py",
    "get_bindings_info"
]