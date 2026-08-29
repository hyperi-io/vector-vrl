"""Shared fixtures: a real Vector binary for subprocess-based tests.

No mocks - tests that need Vector get a REAL vector process, either a
locally-built binary or a container run of the official image. The cascade
(local binary -> docker -> skip) means a dev with `vector` already built runs
fast, CI (which has docker but no local Vector checkout) uses the container,
and an environment with neither reports the test as skipped, never a fake
pass. Hard-fails instead of skipping when $CI is set and docker is
unavailable too - a gate that could not run has not passed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

# renovate: datasource=docker depName=timberio/vector
_VECTOR_TAG = "0.58.0-debian"
_DEFAULT_IMAGE = f"timberio/vector:{_VECTOR_TAG}"

_SUITE_LABEL = "io.hyperi.test.suite=vectordotdev"


def _in_ci() -> bool:
    return bool(os.environ.get("CI"))


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return (
        subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10
        ).returncode
        == 0
    )


def _local_vector_binary() -> Path | None:
    """A locally-built vector binary, if present (fast path for devs)."""
    for candidate in (
        "vector/target/release/vector",
        "vector/target/debug/vector",
        "../vector/target/release/vector",
        "../vector/target/debug/vector",
    ):
        path = Path(candidate)
        if path.is_file():
            return path.resolve()
    found = shutil.which("vector")
    return Path(found) if found else None


def _run_local(binary: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(binary), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def _run_containerized(
    args: list[str], cwd: Path, request: pytest.FixtureRequest
) -> subprocess.CompletedProcess:
    """One-shot `docker run` of the official Vector image against `cwd`.

    `cwd` is mounted at /work and becomes the container's working directory,
    matching how tests already write configs/input under a temp dir and pass
    relative paths to vector.
    """
    image = os.environ.get("VECTORDOTDEV_TEST_VECTOR_IMAGE", _DEFAULT_IMAGE)
    name = "".join(c.lower() if c.isalnum() else "-" for c in request.node.name)
    cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        f"vectordotdev-test-{name}",
        "--label",
        _SUITE_LABEL,
        "--label",
        f"io.hyperi.test.owner-pid={os.getpid()}",
        "-v",
        f"{cwd}:/work",
        "-w",
        "/work",
        image,
        "vector",
        *args,
    ]
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90
    )


@pytest.fixture(scope="session")
def vector_runner(
    request: pytest.FixtureRequest,
) -> Callable[[list[str], Path], subprocess.CompletedProcess]:
    """Returns `run(args, cwd)` - executes `vector <args>` with `cwd` as the
    working directory, using a local binary if available, else a throwaway
    container of the official image, else skips (or fails under CI)."""
    local = _local_vector_binary()
    if local is not None:
        return lambda args, cwd: _run_local(local, args, cwd)

    if _docker_available():
        return lambda args, cwd: _run_containerized(args, cwd, request)

    if _in_ci():
        pytest.fail(
            "no local vector binary and docker is unavailable in CI - "
            "the quality/test image is missing docker, this is an "
            "environment gap, not a real skip"
        )
    pytest.skip("no local vector binary and no docker - install docker to run this test")
