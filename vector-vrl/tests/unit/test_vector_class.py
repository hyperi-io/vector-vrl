"""The `Vector` class and the VRL sandbox guards, through the real bindings.

Everything here runs in-process against the compiled PyO3 module - no
subprocess Vector, no docker, no stubs. Two groups:

- `Vector` construct/initialize/process_logs/get_stats, which had no
  Python-level coverage at all despite being the crate's primary
  hand-written API. Construction is a regression test for the config
  serialisation bug (the dict was serialised with Python `repr()`, so
  anything past `{}` failed to parse as JSON and was rejected).
- The two sandbox guards, exercised the way a caller reaches them
  (`vector_vrl.execute_vrl` / `validate_vrl` / `Vector.process_logs`)
  rather than only through the Rust unit tests: the env/network
  functions must stay undefined, and deep bracket nesting must return an
  error instead of overflowing the parser stack and killing the process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Skip just this module (not the session) when the crate isn't built.
pytest.importorskip(
    "vector_vrl._bindings",
    reason="compiled PyO3 bindings not built - run: cd vector-bindings && maturin develop --release",
)

from vector_vrl import Vector, execute_vrl, validate_vrl  # noqa: E402

# Kept in step with MAX_VRL_NESTING_DEPTH in vector-bindings/src/lib.rs.
MAX_NESTING_DEPTH = 64

# Functions the vrl feature restriction must leave undefined. Each one was
# reachable from caller-supplied VRL before the fix: the first two read the
# host environment, the last two make outbound network requests.
SANDBOX_ESCAPES = [
    pytest.param('.x = get_env_var!("HOME")', id="get_env_var"),
    pytest.param(".x = get_hostname!()", id="get_hostname"),
    pytest.param('.x = http_request!("http://169.254.169.254/")', id="http_request"),
    pytest.param('.x = dns_lookup!("example.com")', id="dns_lookup"),
]


def _nested_vrl(depth: int) -> str:
    return ".x = " + "(" * depth + "true" + ")" * depth


class TestVectorConstruction:
    """Vector(config) accepts real configs, not just an empty dict."""

    @pytest.mark.parametrize(
        "config",
        [
            pytest.param({}, id="empty"),
            pytest.param({"a": 1}, id="single_key"),
            pytest.param(
                {
                    "sources": {"stdin": {"type": "stdin"}},
                    "transforms": {
                        "remap_level": {
                            "type": "remap",
                            "inputs": ["stdin"],
                            "source": ".level = upcase!(.level)",
                        }
                    },
                    "sinks": {
                        "out": {
                            "type": "console",
                            "inputs": ["remap_level"],
                            "encoding": {"codec": "json"},
                        }
                    },
                },
                id="sources_transforms_sinks",
            ),
        ],
    )
    def test_config_dict_is_accepted(self, config):
        assert Vector(config) is not None

    def test_config_with_non_json_python_literals_is_accepted(self):
        """The exact shape `repr()` serialisation used to mangle.

        `repr()` renders these as `True`/`None`/single-quoted strings,
        none of which is valid JSON, so the config was rejected. Only
        `json.dumps` round-trips them.
        """
        config = {
            "enabled": True,
            "disabled": False,
            "unset": None,
            "ratio": 1.5,
            "apostrophe": "it's",
            "nested": {"list": [1, "two", {"three": None}]},
        }
        assert Vector(config) is not None

    def test_malformed_config_value_is_rejected(self):
        """A value json can't serialise fails loudly, not silently."""
        with pytest.raises((TypeError, ValueError)):
            Vector({"handle": object()})


class TestVectorPipeline:
    """initialize / process_logs / get_stats against the real VRL runtime."""

    @staticmethod
    def _initialized() -> Vector:
        pipeline = Vector(
            {
                "transforms": {
                    "remap_level": {
                        "type": "remap",
                        "source": ".level = upcase!(.level)",
                    }
                }
            }
        )
        assert pipeline.initialize() is True
        return pipeline

    def test_process_logs_before_initialize_raises(self):
        pipeline = Vector({"a": 1})
        with pytest.raises(RuntimeError, match="not initialized"):
            pipeline.process_logs(['{"level":"info"}'], ".x = 1")

    def test_process_logs_applies_remap_to_every_event(self):
        """A real multi-event batch through a real remap transform."""
        pipeline = self._initialized()
        logs = [
            json.dumps({"level": "info", "message": "user login"}),
            json.dumps({"level": "error", "message": "auth failed"}),
            json.dumps({"level": "debug", "message": "cache hit"}),
        ]
        vrl = '.level = upcase!(.level)\n.stage = "processed"\n.len = length!(.message)'

        events = pipeline.process_logs(logs, vrl)

        assert len(events) == len(logs)
        # The event's fields come back flattened into the dict, the same as
        # execute_vrl - no "result" JSON string, no "success" wrapper key.
        assert [event["level"] for event in events] == ["INFO", "ERROR", "DEBUG"]
        assert [event["stage"] for event in events] == ["processed"] * 3
        assert [event["len"] for event in events] == [10, 11, 9]
        # The untouched field survives the transform.
        assert events[0]["message"] == "user login"

    def test_process_logs_matches_execute_vrl_shape(self):
        """The two entry points return the same dict for the same event.

        Both run the same VRL runtime, so a caller must not have to care
        which one produced the result (issue #18).
        """
        pipeline = self._initialized()
        # One event that transforms cleanly, one that fails at runtime, so
        # both the success and the error shape are compared.
        logs = [
            json.dumps(
                {"message": '{"ok":true}', "n": 1, "f": 1.5, "b": True, "nul": None}
            ),
            json.dumps({"message": "not json"}),
        ]
        vrl = ".upper = upcase!(.message)\n.parsed = parse_json!(.message)"

        assert pipeline.process_logs(logs, vrl) == execute_vrl(vrl, logs)

    def test_process_logs_reports_runtime_error_per_event(self):
        """A bad event is reported, not dropped and not fatal to the batch."""
        pipeline = self._initialized()
        logs = [
            json.dumps({"message": '{"ok":true}'}),
            json.dumps({"message": "not json"}),
        ]

        results = pipeline.process_logs(logs, ".parsed = parse_json!(.message)")

        assert len(results) == 2
        # Failure is signalled the execute_vrl way: an "error" key replaces
        # the event's fields entirely.
        assert "error" not in results[0]
        assert results[0]["message"] == '{"ok":true}'
        assert "parse_json" in results[1]["error"]
        assert results[1]["original"] == logs[1]
        assert "parsed" not in results[1]

    def test_process_logs_empty_batch_returns_empty(self):
        assert self._initialized().process_logs([], ".x = 1") == []

    def test_process_logs_rejects_uncompilable_vrl(self):
        pipeline = self._initialized()
        with pytest.raises(ValueError, match="VRL compilation failed"):
            pipeline.process_logs(['{"a":1}'], ".x = no_such_function!()")

    def test_get_stats_before_any_work_is_all_zero(self):
        stats = Vector({}).get_stats()

        assert {
            "events_processed",
            "bytes_processed",
            "errors",
            "uptime_seconds",
        } <= set(stats)
        assert all(isinstance(value, int | float) for value in stats.values())
        assert stats["events_processed"] == 0
        assert stats["bytes_processed"] == 0
        assert stats["errors"] == 0
        # Never initialized, so the uptime clock has not started.
        assert stats["uptime_seconds"] == 0.0

    def test_get_stats_counts_real_work(self):
        """The counters track what process_logs actually did."""
        pipeline = self._initialized()
        logs = [json.dumps({"level": "info"}), json.dumps({"level": "error"})]

        pipeline.process_logs(logs, ".level = upcase!(.level)")
        stats = pipeline.get_stats()

        assert stats["events_processed"] == 2
        assert stats["errors"] == 0
        assert stats["bytes_processed"] == sum(len(log.encode()) for log in logs)

    def test_get_stats_accumulates_across_batches(self):
        pipeline = self._initialized()
        log = json.dumps({"level": "info"})

        pipeline.process_logs([log], ".level = upcase!(.level)")
        pipeline.process_logs([log, log], ".level = upcase!(.level)")

        assert pipeline.get_stats()["events_processed"] == 3

    def test_get_stats_counts_per_event_errors_separately(self):
        """A failed event lands in `errors`, not `events_processed`."""
        pipeline = self._initialized()
        logs = [
            json.dumps({"message": '{"ok":true}'}),
            json.dumps({"message": "not json"}),
        ]

        pipeline.process_logs(logs, ".parsed = parse_json!(.message)")
        stats = pipeline.get_stats()

        assert stats["events_processed"] == 1
        assert stats["errors"] == 1
        # Every attempted event is counted exactly once, and its bytes are
        # counted whether or not it transformed cleanly.
        assert stats["events_processed"] + stats["errors"] == len(logs)
        assert stats["bytes_processed"] == sum(len(log.encode()) for log in logs)

    def test_get_stats_uptime_is_real_elapsed_time(self):
        pipeline = self._initialized()
        first = pipeline.get_stats()["uptime_seconds"]
        assert first > 0.0

        time.sleep(0.05)

        assert pipeline.get_stats()["uptime_seconds"] >= first + 0.04

    def test_initialize_restarts_the_counters(self):
        """Stats describe the run since the most recent initialize()."""
        pipeline = self._initialized()
        pipeline.process_logs(
            [json.dumps({"level": "info"})], ".level = upcase!(.level)"
        )
        assert pipeline.get_stats()["events_processed"] == 1

        pipeline.initialize()

        stats = pipeline.get_stats()
        assert stats["events_processed"] == 0
        assert stats["bytes_processed"] == 0
        assert stats["errors"] == 0

    def test_get_stats_unmoved_by_a_compile_failure(self):
        """Compilation fails before any event is touched, so nothing counts."""
        pipeline = self._initialized()
        with pytest.raises(ValueError, match="VRL compilation failed"):
            pipeline.process_logs(['{"a":1}'], ".x = no_such_function!()")

        stats = pipeline.get_stats()
        assert stats["events_processed"] == 0
        assert stats["errors"] == 0
        assert stats["bytes_processed"] == 0


class TestVrlSandbox:
    """Env-reading and network VRL functions stay unreachable."""

    @pytest.mark.parametrize("vrl", SANDBOX_ESCAPES)
    def test_validate_vrl_rejects_escape(self, vrl):
        result = validate_vrl(vrl)
        assert result.success is False, f"{vrl!r} compiled - the sandbox is open"
        assert "undefined function" in result.error

    @pytest.mark.parametrize("vrl", SANDBOX_ESCAPES)
    def test_execute_vrl_rejects_escape(self, vrl):
        with pytest.raises(ValueError, match="VRL compilation failed"):
            execute_vrl(vrl, [json.dumps({"a": 1})])

    @pytest.mark.parametrize("vrl", SANDBOX_ESCAPES)
    def test_vector_process_logs_rejects_escape(self, vrl):
        pipeline = Vector({})
        pipeline.initialize()
        with pytest.raises(ValueError, match="VRL compilation failed"):
            pipeline.process_logs([json.dumps({"a": 1})], vrl)

    def test_ordinary_vrl_still_compiles_and_runs(self):
        """Positive control: the guards reject those four, not everything.

        Without this the sandbox assertions above would still pass if VRL
        compilation broke outright.
        """
        results = execute_vrl(
            '.parsed = parse_json!(.message)\n.upper = upcase!("ok")\n.at = now()',
            [json.dumps({"message": '{"k":"v"}'})],
        )
        assert len(results) == 1
        assert results[0]["upper"] == "OK"
        assert "at" in results[0]


class TestVrlNestingDepth:
    """Deep bracket nesting is rejected instead of overflowing the stack."""

    def test_validate_vrl_rejects_thousand_deep_nesting(self):
        result = validate_vrl(_nested_vrl(1000))
        assert result.success is False
        assert "nests" in result.error, f"unexpected rejection reason: {result.error}"

    def test_execute_vrl_rejects_thousand_deep_nesting(self):
        with pytest.raises(ValueError, match="nests"):
            execute_vrl(_nested_vrl(1000), [json.dumps({"a": 1})])

    def test_nesting_at_the_limit_is_accepted(self):
        """Boundary: the guard rejects past the limit, not at it."""
        assert validate_vrl(_nested_vrl(MAX_NESTING_DEPTH)).success is True

    def test_nesting_one_past_the_limit_is_rejected(self):
        result = validate_vrl(_nested_vrl(MAX_NESTING_DEPTH + 1))
        assert result.success is False
        assert "nests" in result.error

    def test_deep_nesting_does_not_kill_the_interpreter(self):
        """Isolated so a regression fails this test, not the whole run.

        A stack overflow in the VRL parser is a SIGSEGV, which no Python
        `except` can catch - in-process it would take the pytest session
        down with it and destroy every other result. Run it in a child
        interpreter and assert the child exited cleanly.
        """
        script = "\n".join(
            [
                f"import sys; sys.path.insert(0, {str(_SRC)!r})",
                "from vector_vrl import validate_vrl",
                "r = validate_vrl('.x = ' + '(' * 1000 + 'true' + ')' * 1000)",
                "assert r.success is False, 'deeply nested VRL compiled'",
                "assert 'nests' in r.error, r.error",
                "print('rejected cleanly')",
            ]
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(_SRC), *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])]
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=env,
        )

        assert completed.returncode == 0, (
            f"child interpreter exited {completed.returncode} "
            f"(negative means killed by a signal - the depth guard is gone)\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
        assert "rejected cleanly" in completed.stdout
