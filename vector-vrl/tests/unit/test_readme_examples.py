"""Execute the code the READMEs tell people to run.

The hero example is the first thing anyone copies off the PyPI page, and a
rename once left it reading `from vector-vrl import ...` - which is not valid
Python at all. Ruff formatted it happily and the whole gate stayed green,
because nothing ran it. This runs it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PACKAGE_README = Path(__file__).parent.parent.parent / "README.md"
ROOT_README = PACKAGE_README.parent.parent / "README.md"

BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _blocks(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    return [
        (f"{path.name}-{i}", src)
        for i, src in enumerate(BLOCK.findall(path.read_text(encoding="utf-8")))
    ]


CASES = _blocks(PACKAGE_README) + _blocks(ROOT_README)


def test_the_readmes_were_found():
    """A silent empty case list would make this suite prove nothing."""
    assert CASES, "no python blocks found - the READMEs moved or the fence changed"


@pytest.mark.parametrize(("name", "source"), CASES, ids=[c[0] for c in CASES])
def test_readme_block_runs(name: str, source: str):
    # `>>>` blocks are transcripts of a session, not a script to execute.
    if source.lstrip().startswith(">>>"):
        pytest.skip("doctest-style transcript, not a runnable block")
    compile(source, name, "exec")
    exec(source, {"__name__": "__readme__"})  # noqa: S102 - running our own docs
