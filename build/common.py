"""
Common types and utilities for vectordotdev build system
"""

import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum

class BuildStage(Enum):
    VECTOR_CORE = "vector_core"
    VECTOR_BINDINGS = "vector_bindings" 
    PYTHON_BINDINGS = "python_bindings"

class ErrorType(Enum):
    UPSTREAM_COMPILE = "upstream_compile"
    VECTOR_CORE_FAILURE = "vector_core_failure"
    BINDING_FAILURE = "binding_failure"
    PYTHON_FAILURE = "python_failure"
    DEPENDENCY_FAILURE = "dependency_failure"
    OUR_CODE_FAILURE = "our_code_failure"
    UNKNOWN_FAILURE = "unknown_failure"

@dataclass
class StageResult:
    stage: BuildStage
    success: bool
    build_time: float
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None

@dataclass
class BuildResult:
    success: bool
    vector_version: str
    total_time: float
    stage_results: Dict[BuildStage, StageResult]

def log_message(message: str):
    """Console logging with emojis (following emoji policy for UI)"""
    timestamp = time.strftime('%H:%M:%S')
    print(f"[{timestamp}] {message}")  # Console: emojis OK per policy