"""
regex2vrl - Convert regex and grok patterns to performant VRL code
Core conversion module for Python integration
Version: 2.0.0 - Production Ready
"""

# Import main conversion classes
from .core import RegexToVRL, PatternType, PatternAnalysis
from .grok_converter import GrokToVRL
from .working_vrl_engine import WorkingVRLEngine

# Version information
__version__ = "2.0.0"
__author__ = "vectordotdev"

# Export main API
__all__ = [
    'RegexToVRL',
    'GrokToVRL', 
    'WorkingVRLEngine',
    'PatternType',
    'PatternAnalysis',
    '__version__'
]