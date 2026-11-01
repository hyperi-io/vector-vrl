"""Run VRL through a real `vector` binary, configured by file, fed on stdin."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 60.0


def remap_chain(config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """The remap transforms of a Vector config, in the order events pass them.

    The config's sources and sinks are not used: the runner feeds the events
    in and collects what comes out. Transforms must form one chain through
    their `inputs`, and each must be a `remap` with its VRL inline.

    Raises:
        ValueError: the config has no transforms, one is not an inline
            remap, or they do not form a single chain.
    """
    transforms = config.get("transforms")
    if not isinstance(transforms, dict) or not transforms:
        raise ValueError("the config has no transforms to run")
    for name, transform in transforms.items():
        if not isinstance(transform, dict) or transform.get("type") != "remap":
            raise ValueError(f"transform {name!r} is not a remap")
        if not isinstance(transform.get("source"), str):
            raise ValueError(f"remap {name!r} has no inline source")

    def upstream(name: str) -> list[str]:
        inputs = transforms[name].get("inputs") or []
        return [i for i in inputs if i in transforms]

    heads = [name for name in transforms if not upstream(name)]
    following = {
        name: [n for n in transforms if name in upstream(n)] for name in transforms
    }
    if (
        len(heads) != 1
        or any(len(upstream(n)) > 1 for n in transforms)
        or any(len(after) > 1 for after in following.values())
    ):
        raise ValueError("the remap transforms must form one chain through `inputs`")

    order = [heads[0]]
    while following[order[-1]]:
        order.append(following[order[-1]][0])
    if len(order) != len(transforms):
        raise ValueError("the remap transforms must form one chain through `inputs`")
    return [(name, transforms[name]) for name in order]


class VectorTestRunner:
    """Centralized Vector test runner that handles shell escaping and configuration properly.

    NO shell escaping issues - uses file-based communication only.
    """

    def __init__(self, vector_binary: str | None = None, verbose: bool = False):
        """Resolve the Vector binary (PATH first, then /usr/bin/vector) and set up state."""
        self.vector_binary = (
            vector_binary or shutil.which("vector") or "/usr/bin/vector"
        )
        self.verbose = verbose

        if not Path(self.vector_binary).exists():
            raise RuntimeError(f"Vector binary not found: {self.vector_binary}")

    def test_vrl_with_vector(
        self,
        vrl_code: str,
        input_logs: list[str],
        test_name: str = "test",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> tuple[bool, list[dict], str]:
        """Run `vrl_code` as one remap transform over `input_logs` in a real Vector.

        Returns:
            (success, results, error_message), as `run_remap_chain` does.
        """
        return self.run_remap_chain(
            [("vrl_test", {"type": "remap", "source": vrl_code})],
            input_logs,
            test_name,
            timeout,
        )

    def run_remap_chain(
        self,
        transforms: list[tuple[str, dict[str, Any]]],
        input_logs: list[str],
        test_name: str = "test",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> tuple[bool, list[dict], str]:
        """Run `input_logs` through `transforms`, in order, in a real Vector.

        Vector reads the logs from stdin and exits once every event is written,
        so the run ends when the work does. `timeout` bounds it: a run still
        going then is killed and reported as a failure.

        Each transform keeps its own options (`drop_on_error`, `drop_on_abort`
        and so on), and only its `inputs` is rewired to the one before it.

        Returns:
            (success, results, error_message). `success` means Vector exited 0
            and every output line was JSON. An event a program aborts is
            dropped by Vector, so `results` can be shorter than `input_logs`.
            `error_message` carries Vector's stderr, including the VRL runtime
            errors of a successful run.
        """
        test_dir = Path(tempfile.mkdtemp(prefix=f"vector_test_{test_name}_"))
        try:
            data_dir = test_dir / "vector_data"
            data_dir.mkdir()
            config_file = test_dir / "config.json"
            config_file.write_text(
                json.dumps(self._vector_config(transforms, data_dir)),
                encoding="utf-8",
                newline="\n",
            )
            if self.verbose:
                print(f"   Test: {test_name}, {len(input_logs)} logs, dir {test_dir}")

            try:
                # An argv list with no shell, reading a config this runner wrote.
                # `-qq` keeps Vector's own logging to errors.
                completed = subprocess.run(  # noqa: S603
                    [self.vector_binary, "-qq", "--config", str(config_file)],
                    input="".join(f"{log}\n" for log in input_logs),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return False, [], f"Vector did not finish within {timeout}s"
            except OSError as error:
                return False, [], f"Vector execution error: {error}"

            results: list[dict] = []
            undecodable: list[int] = []
            for number, line in enumerate(completed.stdout.splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    undecodable.append(number)

            problems = []
            if completed.returncode != 0:
                problems.append(f"Vector exited {completed.returncode}")
            if undecodable:
                problems.append(f"output lines {undecodable[:5]} are not JSON")
            if completed.stderr.strip():
                problems.append(completed.stderr.strip()[:500])
            success = completed.returncode == 0 and not undecodable

            if self.verbose:
                outcome = "SUCCESS" if success else "FAILED"
                print(f"   {outcome}: {len(results)}/{len(input_logs)} events back")
            return success, results, " | ".join(problems)
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    @staticmethod
    def _vector_config(
        transforms: list[tuple[str, dict[str, Any]]], data_dir: Path
    ) -> dict[str, Any]:
        """A stdin -> transforms -> stdout Vector config, transforms chained in order."""
        chained: dict[str, Any] = {}
        upstream = "runner_stdin"
        for name, transform in transforms:
            chained[name] = {**transform, "inputs": [upstream]}
            upstream = name
        return {
            "data_dir": str(data_dir),
            "sources": {"runner_stdin": {"type": "stdin"}},
            "transforms": chained,
            "sinks": {
                "runner_stdout": {
                    "type": "console",
                    "inputs": [upstream],
                    "encoding": {"codec": "json"},
                }
            },
            "api": {"enabled": False},
        }

    def validate_field_extraction(
        self, results: list[dict], expected_fields: list[str]
    ) -> dict[str, Any]:
        """Validate that expected fields were extracted from results.

        Returns validation report with field-by-field analysis.
        """
        if not results:
            return {
                "success": False,
                "extracted_fields": [],
                "missing_fields": expected_fields,
                "field_count": 0,
                "extraction_rate": 0.0,
            }

        # Check which expected fields were found
        extracted_fields = []
        missing_fields = []

        # Combine all result keys to see what was extracted
        all_fields = set()
        for result in results:
            all_fields.update(result.keys())

        for field in expected_fields:
            if any(field in result for result in results):
                extracted_fields.append(field)
            else:
                missing_fields.append(field)

        extraction_rate = (
            (len(extracted_fields) / len(expected_fields) * 100)
            if expected_fields
            else 0
        )

        return {
            "success": len(missing_fields) == 0,
            "extracted_fields": extracted_fields,
            "missing_fields": missing_fields,
            "field_count": len(extracted_fields),
            "extraction_rate": extraction_rate,
            "total_result_fields": list(all_fields),
            "sample_result": results[0] if results else {},
        }


def test_vrl_simple(
    vrl_code: str,
    input_logs: list[str],
    expected_fields: list[str] | None = None,
    test_name: str = "simple_test",
) -> dict[str, Any]:
    """Simple function to test VRL code with Vector CLI.

    Returns comprehensive test results with field validation.
    """
    runner = VectorTestRunner(verbose=True)
    success, results, error = runner.test_vrl_with_vector(
        vrl_code, input_logs, test_name
    )

    # Validate field extraction if expected fields provided
    field_validation = {}
    if expected_fields:
        field_validation = runner.validate_field_extraction(results, expected_fields)

    return {
        "success": success,
        "input_count": len(input_logs),
        "output_count": len(results),
        "results": results,
        "error": error,
        "field_validation": field_validation,
        "vrl_code": vrl_code,
    }


# Example usage and testing
if __name__ == "__main__":
    print("Testing VectorTestRunner utility")

    # Test 1: Simple VRL
    simple_result = test_vrl_simple(
        'message_str = to_string(.message) ?? ""; .test = "working"; .processed = true',
        ["Test log message"],
        ["test", "processed"],
        "utility_test",
    )

    print(f"Simple test: {'PASS' if simple_result['success'] else 'FAIL'}")
    if simple_result["field_validation"]:
        print(
            f"   Fields: {simple_result['field_validation']['field_count']}/{len(simple_result['field_validation']['extracted_fields'] + simple_result['field_validation']['missing_fields'])}"
        )
