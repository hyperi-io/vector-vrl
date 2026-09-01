"""Install a just-built wheel into a throwaway venv and prove it actually works.

The "hero test" - the golden path a real `pip install vector-vrl` user
hits first, run against the actual wheel artifact rather than the dev tree
(which has its own compiled `.so` sitting in `src/vector_vrl/_bindings/`
and would happily hide a wheel that shipped broken). Runs from a temp
directory outside the repo so nothing here can shadow the installed
package, and fails loudly if the compiled extension did not make it into
the wheel - `get_bindings_info()['source']` must be `bundled`, never
`external` or `none`.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

_PYTHON_TAG_RE = re.compile(r"^cp(\d)(\d+)$")


def _python_version_for(wheel: Path) -> str:
    """The CPython version (e.g. "3.12") a wheel's own filename tag names.

    A wheel is tied to the exact interpreter it was built against unless
    tagged abi3 - installing it into a mismatched venv fails outright, and
    the CI runner's ambient default Python is not guaranteed to match
    whatever maturin-action picked, so this must be read from the wheel
    itself rather than assumed.
    """
    python_tag = wheel.stem.split("-")[2]
    match = _PYTHON_TAG_RE.match(python_tag)
    if not match:
        raise ValueError(
            f"can't parse a CPython version from wheel tag {python_tag!r} ({wheel.name})"
        )
    return f"{match.group(1)}.{match.group(2)}"


# Mirrors README.md's worked example and the Vector class golden path.
SMOKE_SCRIPT = r'''
from pathlib import Path

import vector_vrl

info = vector_vrl.get_bindings_info()
assert info["source"] == "bundled", f"compiled bindings not bundled: {info}"

package = Path(vector_vrl.__file__).parent
assert (package / "py.typed").is_file(), "py.typed marker missing from the wheel"
assert (package / "_bindings" / "vector_bindings.pyi").is_file(), (
    "vector_bindings.pyi stub missing from the wheel"
)

vrl = """
parsed, err = parse_json(.message)
if err == null {
    .level = parsed.level
}
"""
events = ['{"message": "{\\"level\\": \\"info\\"}"}']
result = vector_vrl.execute_vrl(vrl, events)
assert result == [{"message": '{"level": "info"}', "level": "info"}], f"execute_vrl gave {result!r}"

ok = vector_vrl.validate_vrl(".level = upcase!(.level)")
assert ok.success is True, f"validate_vrl rejected good VRL: {ok.error}"

bad = vector_vrl.validate_vrl(".a = ")
assert bad.success is False, "validate_vrl accepted syntactically bad VRL"

pipeline = vector_vrl.Vector({})
pipeline.initialize()
logs = pipeline.process_logs(['{"level":"info"}'], ".level = upcase!(.level)")
assert logs == [{"level": "INFO"}], f"Vector.process_logs gave {logs!r}"
stats = pipeline.get_stats()
assert stats["events_processed"] == 1, f"get_stats gave {stats!r}"

print("hero smoke test: OK -", info)
'''


def main() -> int:
    """Install the newest wheel in `dist_dir` (argv[1]) and run SMOKE_SCRIPT against it."""
    if len(sys.argv) != 2:
        print("usage: wheel_smoke_check.py <dist-dir>", file=sys.stderr)
        return 2

    wheels = sorted(Path(sys.argv[1]).glob("*.whl"))
    if not wheels:
        print(f"no .whl found in {sys.argv[1]}", file=sys.stderr)
        return 1
    wheel = wheels[-1]

    py_version = _python_version_for(wheel)
    with tempfile.TemporaryDirectory() as tmp:
        venv_dir = Path(tmp) / "venv"
        subprocess.run(
            ["uv", "venv", "--python", py_version, str(venv_dir)], check=True
        )
        python = venv_dir / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(wheel)], check=True
        )
        result = subprocess.run([str(python), "-c", SMOKE_SCRIPT], cwd=tmp)
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
