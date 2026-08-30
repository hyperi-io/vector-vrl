"""Common types and utilities for vector-vrl build system."""

import time
from dataclasses import dataclass
from enum import Enum


class BuildStage(Enum):
    """Identifies one of the three build stages: Vector, bindings, or Python."""

    VECTOR_CORE = "vector_core"
    VECTOR_BINDINGS = "vector_bindings"
    PYTHON_BINDINGS = "python_bindings"


class ErrorType(Enum):
    """Categorizes a build failure by which layer caused it."""

    UPSTREAM_COMPILE = "upstream_compile"
    VECTOR_CORE_FAILURE = "vector_core_failure"
    BINDING_FAILURE = "binding_failure"
    PYTHON_FAILURE = "python_failure"
    DEPENDENCY_FAILURE = "dependency_failure"
    OUR_CODE_FAILURE = "our_code_failure"
    UNKNOWN_FAILURE = "unknown_failure"


@dataclass
class StageResult:
    """Outcome of a single build stage: success, timing, and any error."""

    stage: BuildStage
    success: bool
    build_time: float
    error_type: ErrorType | None = None
    error_message: str | None = None


@dataclass
class BuildResult:
    """Overall outcome of the 3-stage build, including per-stage results."""

    success: bool
    vector_version: str
    total_time: float
    stage_results: dict[BuildStage, StageResult]


def log_message(message: str):
    """Console logging with emojis (following emoji policy for UI)."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")  # Console: emojis OK per policy
