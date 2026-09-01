"""Binary-gated fixture for the subprocess surface.

`VectorTestRunner` and the THG assessor shell out to a `vector` binary found
on PATH - there is no container path - so these tests need one installed:
skipped where there is none, a hard failure under `$CI`, the same rule the
root conftest applies to its docker cascade.
"""

import os
import shutil

import pytest


@pytest.fixture(scope="session")
def vector_binary() -> str:
    found = shutil.which("vector")
    if found:
        return found
    if os.environ.get("CI"):
        pytest.fail(
            "no vector binary on PATH in CI - the subprocess surface shells out "
            "to a binary, so this is an environment gap, not a real skip"
        )
    pytest.skip("no vector binary on PATH - install one to run this test")
