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
import zipfile
from email.parser import BytesParser
from pathlib import Path

_PYTHON_TAG_RE = re.compile(r"^cp(\d)(\d+)$")
_REQUIRES_FLOOR_RE = re.compile(r">=\s*(\d+)\.(\d+)")


def _tag_version(wheel: Path) -> tuple[int, int]:
    """The CPython version a wheel's own filename tag names, as (major, minor)."""
    python_tag = wheel.stem.split("-")[2]
    match = _PYTHON_TAG_RE.match(python_tag)
    if not match:
        raise ValueError(
            f"can't parse a CPython version from wheel tag {python_tag!r} ({wheel.name})"
        )
    return int(match.group(1)), int(match.group(2))


def _requires_python_floor(wheel: Path) -> tuple[int, int] | None:
    """The lower bound of the wheel's own ``Requires-Python``, if it declares one."""
    with zipfile.ZipFile(wheel) as archive:
        names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if not names:
            return None
        with archive.open(names[0]) as handle:
            metadata = BytesParser().parse(handle, headersonly=True)
    declared = metadata.get("Requires-Python")
    if not declared:
        return None
    match = _REQUIRES_FLOOR_RE.search(declared)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _python_version_for(wheel: Path) -> str:
    """The CPython version (e.g. "3.14") to build the throwaway venv on.

    Two constraints, and the venv must satisfy both. The filename tag names
    the interpreter a non-abi3 wheel is tied to, and the CI runner's ambient
    default is not guaranteed to match whatever maturin-action picked. An
    abi3 wheel is forward compatible, so there its tag is a FLOOR rather than
    an exact requirement, and the package's own ``Requires-Python`` can sit
    above it -- an abi3-py312 wheel declaring >=3.14 refuses to install on
    3.12, which is the wheel telling the truth and the tag being the lesser
    of the two bounds.
    """
    tag = _tag_version(wheel)
    floor = _requires_python_floor(wheel)
    major, minor = max(tag, floor) if floor else tag
    return f"{major}.{minor}"


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
