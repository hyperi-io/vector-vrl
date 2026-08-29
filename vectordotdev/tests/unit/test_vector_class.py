"""The `Vector` class and the VRL sandbox guards, through the real bindings.

Everything here runs in-process against the compiled PyO3 module - no
subprocess Vector, no docker, no stubs. Two groups:

- `Vector` construct/initialize/process_logs/get_stats, which had no
  Python-level coverage at all despite being the crate's primary
  hand-written API. Construction is a regression test for the config
  serialisation bug (the dict was serialised with Python `repr()`, so
  anything past `{}` failed to parse as JSON and was rejected).
- The two sandbox guards, exercised the way a caller reaches them
  (`vectordotdev.execute_vrl` / `validate_vrl` / `Vector.process_logs`)
  rather than only through the Rust unit tests: the env/network
  functions must stay undefined, and deep bracket nesting must return an
  error instead of overflowing the parser stack and killing the process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Skip just this module (not the session) when the crate isn't built.
pytest.importorskip(
    "vectordotdev._bindings",
    reason="compiled PyO3 bindings not built - run: cd vector-bindings && maturin develop --release",
)

from vectordotdev import Vector, execute_vrl, validate_vrl  # noqa: E402

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
                    "remap_level": {"type": "remap", "source": ".level = upcase!(.level)"}
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

        results = pipeline.process_logs(logs, vrl)

        assert len(results) == len(logs)
        # process_logs returns {"result": <json string>, "success": bool} -
        # note this differs from execute_vrl, which returns the event's
        # fields flattened into the dict.
        events = [json.loads(item["result"]) for item in results]
        assert all(item["success"] is True for item in results)
        assert [event["level"] for event in events] == ["INFO", "ERROR", "DEBUG"]
        assert [event["stage"] for event in events] == ["processed"] * 3
        assert [event["len"] for event in events] == [10, 11, 9]
        # The untouched field survives the transform.
        assert events[0]["message"] == "user login"

    def test_process_logs_reports_runtime_error_per_event(self):
        """A bad event is reported, not dropped and not fatal to the batch."""
        pipeline = self._initialized()
        logs = [json.dumps({"message": '{"ok":true}'}), json.dumps({"message": "not json"})]

        results = pipeline.process_logs(logs, ".parsed = parse_json!(.message)")

        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "parse_json" in results[1]["error"]
        assert results[1]["original"] == logs[1]

    def test_process_logs_empty_batch_returns_empty(self):
        assert self._initialized().process_logs([], ".x = 1") == []

    def test_process_logs_rejects_uncompilable_vrl(self):
        pipeline = self._initialized()
        with pytest.raises(ValueError, match="VRL compilation failed"):
            pipeline.process_logs(['{"a":1}'], ".x = no_such_function!()")

    def test_get_stats_returns_dict(self):
        pipeline = self._initialized()
        pipeline.process_logs([json.dumps({"level": "info"})], ".level = upcase!(.level)")

        stats = pipeline.get_stats()

        assert isinstance(stats, dict)
        # Only the shape is asserted: the counters are hardcoded zeros in
        # the crate and do not yet track real work, so asserting values
        # here would enshrine that as intended behaviour.
        assert {"events_processed", "bytes_processed", "errors", "uptime_seconds"} <= set(
            stats
        )
        assert all(isinstance(value, int | float) for value in stats.values())


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
                "from vectordotdev import validate_vrl",
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
