"""Unit tests for wheel_smoke_check.py's interpreter choice.

No mocks - each test writes a real .whl (a zip carrying a real dist-info
METADATA) and the code under test reads it exactly as it reads a wheel
maturin produced. The install and the smoke run itself need a real
interpreter and a real compiled extension, so they are exercised by the
CI job that runs this script against the built dist/, not here.
"""

import zipfile
from pathlib import Path

import pytest

from wheel_smoke_check import _python_version_for, _requires_python_floor, _tag_version


def _wheel(tmp_path: Path, name: str, requires_python: str | None) -> Path:
    """A real wheel file: the filename tag plus a dist-info METADATA."""
    path = tmp_path / name
    metadata = "Metadata-Version: 2.1\nName: vector-vrl\nVersion: 1.0.8\n"
    if requires_python is not None:
        metadata += f"Requires-Python: {requires_python}\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("vector_vrl-1.0.8.dist-info/METADATA", metadata)
    return path


class TestTagVersion:
    """The CPython version the filename tag names."""

    def test_reads_the_tag(self, tmp_path):
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-cp312-abi3-linux_x86_64.whl", None)
        assert _tag_version(wheel) == (3, 12)

    def test_reads_a_two_digit_minor(self, tmp_path):
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-cp314-abi3-linux_x86_64.whl", None)
        assert _tag_version(wheel) == (3, 14)

    def test_refuses_a_tag_it_cannot_parse(self, tmp_path):
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-py3-none-any.whl", None)
        with pytest.raises(ValueError, match="can't parse a CPython version"):
            _tag_version(wheel)


class TestRequiresPythonFloor:
    """The lower bound the wheel's own metadata declares."""

    def test_reads_the_floor(self, tmp_path):
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-cp312-abi3-linux_x86_64.whl", ">=3.14")
        assert _requires_python_floor(wheel) == (3, 14)

    def test_tolerates_whitespace(self, tmp_path):
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-cp312-abi3-linux_x86_64.whl", ">= 3.14")
        assert _requires_python_floor(wheel) == (3, 14)

    def test_none_when_undeclared(self, tmp_path):
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-cp312-abi3-linux_x86_64.whl", None)
        assert _requires_python_floor(wheel) is None

    def test_none_when_the_bound_has_no_lower_half(self, tmp_path):
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-cp312-abi3-linux_x86_64.whl", "<4.0")
        assert _requires_python_floor(wheel) is None


class TestPythonVersionFor:
    """The venv must satisfy both bounds, and the abi3 tag is the lesser one."""

    def test_the_declared_floor_wins_over_an_abi3_tag(self, tmp_path):
        # The 1.0.8 release: abi3-py312 wheel, >=3.14 metadata. Building the
        # venv on the tag gave a 3.12 interpreter the wheel then refused.
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-cp312-abi3-linux_x86_64.whl", ">=3.14")
        assert _python_version_for(wheel) == "3.14"

    def test_the_tag_wins_when_it_is_the_higher_bound(self, tmp_path):
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-cp314-abi3-linux_x86_64.whl", ">=3.12")
        assert _python_version_for(wheel) == "3.14"

    def test_the_tag_stands_alone_when_nothing_is_declared(self, tmp_path):
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-cp312-abi3-linux_x86_64.whl", None)
        assert _python_version_for(wheel) == "3.12"

    def test_equal_bounds_agree(self, tmp_path):
        wheel = _wheel(tmp_path, "vector_vrl-1.0.8-cp314-abi3-linux_x86_64.whl", ">=3.14")
        assert _python_version_for(wheel) == "3.14"
