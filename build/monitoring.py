"""Intelligent build monitoring for vector-vrl."""

import re
import time
from dataclasses import dataclass
from pathlib import Path

from common import ErrorType, log_message


@dataclass(frozen=True)
class BuildPhase:
    """A build-log phase: the regex that marks it, and how long it may run."""

    pattern: str
    max_duration: int = 300


class BuildMonitor:
    """Intelligent build monitoring with pattern-based progress and error detection."""

    # Stage-specific error patterns
    UPSTREAM_PATTERNS = [
        r"cannot find function.*proto_to_value.*vrl.*protobuf",
        r"cannot find function.*get_message_descriptor.*vrl.*protobuf",
        r"cannot find function.*encode_message.*vrl.*protobuf",
        r"error: could not compile.*codecs.*due to.*previous error",
        r"krb5.*make failed",
        r"make failed in lib",
        r"auth_none\.c.*too many arguments to function",
        r"thread 'main' panicked at.*krb5-src",
    ]

    def __init__(self, stall_timeout: int = 600, verbose: bool = False):
        """Set up the stall timeout and verbosity for build monitoring."""
        self.stall_timeout = stall_timeout  # 10 minutes default
        self.verbose = verbose

    def analyze_stage_error(self, build_log: str) -> tuple:
        """Analyze build errors and categorize them."""
        for pattern in self.UPSTREAM_PATTERNS:
            if re.search(pattern, build_log, re.IGNORECASE | re.MULTILINE):
                return ErrorType.UPSTREAM_COMPILE, f"Upstream: {pattern[:30]}..."

        if re.search(
            r"dependency resolution|failed to select", build_log, re.IGNORECASE
        ):
            return ErrorType.DEPENDENCY_FAILURE, "Dependency conflict"

        return ErrorType.OUR_CODE_FAILURE, "Code issue"

    def monitor_intelligent_build(self, process, name: str, log_file: Path) -> bool:
        """Intelligent build monitoring with pattern-based progress and error detection."""
        log_message(f"Monitoring {name} with intelligent detection...")

        last_activity = time.time()
        last_size = 0
        last_meaningful_output = time.time()

        # Track build phases with configurable durations
        build_phases = {
            "downloading": BuildPhase(r"Downloading|Updating", max_duration=900),
            "compiling": BuildPhase(r"Compiling", max_duration=1800),
            "linking": BuildPhase(r"Linking|Finished", max_duration=600),
            "error": BuildPhase(r"error:|ERROR:|failed|panic"),
        }

        current_phase = None
        phase_start_time = time.time()
        error_indicators = []

        while process.poll() is None:
            try:
                if log_file.exists():
                    current_size = log_file.stat().st_size

                    if current_size > last_size:
                        last_activity = time.time()

                        # Read new content and analyze
                        with open(log_file) as f:
                            f.seek(last_size)
                            new_content = f.read()
                            last_size = current_size

                        # Analyze new content for phases and errors
                        for line in new_content.split("\n"):
                            line = line.strip()
                            if not line:
                                continue

                            # Check for meaningful progress
                            if any(
                                keyword in line
                                for keyword in [
                                    "Compiling",
                                    "Downloading",
                                    "Building",
                                    "Finished",
                                ]
                            ):
                                last_meaningful_output = time.time()

                                if self.verbose:
                                    log_message(f"  -> {line[:60]}")

                            # Detect build phases
                            for phase_name, phase_info in build_phases.items():
                                if re.search(phase_info.pattern, line, re.IGNORECASE):
                                    if current_phase != phase_name:
                                        if current_phase:
                                            elapsed = time.time() - phase_start_time
                                            log_message(
                                                f"  {current_phase} completed in {elapsed:.1f}s"
                                            )

                                        current_phase = phase_name
                                        phase_start_time = time.time()
                                        log_message(f"  Entering {phase_name} phase...")

                            # Check for error patterns
                            for pattern in self.UPSTREAM_PATTERNS:
                                if re.search(pattern, line, re.IGNORECASE):
                                    error_indicators.append(line[:100])
                                    log_message(
                                        f"  Detected upstream issue: {line[:80]}"
                                    )

                                    # Immediate termination on certain errors
                                    if any(
                                        fatal in pattern
                                        for fatal in ["make failed", "panic"]
                                    ):
                                        log_message(
                                            "  Fatal upstream error detected - terminating build"
                                        )
                                        process.terminate()
                                        return False

                    # Intelligent stall detection
                    time_since_activity = time.time() - last_activity
                    time_since_meaningful = time.time() - last_meaningful_output

                    # Phase-specific timeout
                    if current_phase and current_phase in build_phases:
                        phase_duration = time.time() - phase_start_time
                        max_phase_duration = build_phases[current_phase].max_duration

                        if phase_duration > max_phase_duration:
                            log_message(
                                f"  {current_phase} phase exceeded {max_phase_duration}s - likely hung"
                            )
                            process.terminate()
                            return False

                    # No meaningful progress timeout (generous for Vector builds)
                    if time_since_meaningful > 900:  # 15 minutes no meaningful progress
                        log_message(
                            f"  No meaningful progress for {time_since_meaningful:.0f}s - likely hung"
                        )
                        process.terminate()
                        return False

                    # Basic heartbeat fallback
                    if time_since_activity > self.stall_timeout:
                        log_message(
                            f"  Complete stall for {time_since_activity:.0f}s - terminating"
                        )
                        process.terminate()
                        return False

            except Exception as e:
                if self.verbose:
                    log_message(f"  Monitor error: {e}")

            time.sleep(2)  # Check every 2 seconds

        # Process finished - check result
        return_code = process.wait()

        if current_phase:
            elapsed = time.time() - phase_start_time
            log_message(f"  {current_phase} completed in {elapsed:.1f}s")

        # Check if we collected any error indicators
        if return_code != 0 and error_indicators:
            log_message(f"  Error patterns detected: {len(error_indicators)} issues")
            for error in error_indicators[:3]:  # Show first 3 errors
                log_message(f"    • {error}")

        return return_code == 0
