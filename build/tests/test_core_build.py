"""The Python-layer check at the end of a build.

It once ran `import vector`, a module this repo does not provide, so a clean
build failed its last stage and any unrelated `vector` on the path passed it.
Each case runs a real interpreter against modules written to a temp dir.
"""

import sys
from pathlib import Path

import pytest

from core_build import verify_python_layer


@pytest.mark.parametrize(
    ("modules", "passes"),
    [
        pytest.param({"vector.py": ""}, False, id="unrelated_vector_module"),
        pytest.param({}, False, id="no_vector_vrl"),
        pytest.param(
            {
                "vector_vrl/__init__.py": (
                    "def get_bindings_info():\n"
                    "    return {'bundled': False}\n"
                    "def execute_vrl(code, events):\n"
                    "    raise ImportError('VRL bindings not available')\n"
                )
            },
            False,
            id="bindings_missing",
        ),
        pytest.param(
            {
                "vector_vrl/__init__.py": (
                    "def get_bindings_info():\n"
                    "    return {'bundled': True}\n"
                    "def execute_vrl(code, events):\n"
                    "    return [{'ok': True} for _ in events]\n"
                )
            },
            True,
            id="bundled_and_runs",
        ),
    ],
)
def test_the_check_needs_vector_vrl_with_working_bindings(tmp_path, modules, passes):
    for name, source in modules.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    assert verify_python_layer(Path(sys.executable), tmp_path) is passes


def test_a_missing_interpreter_fails_the_check(tmp_path):
    assert verify_python_layer(tmp_path / "no-such-python", tmp_path) is False
