"""
Check and update the Vector version this repo builds and tests against.

Two independent pins:
- the `vector/` checkout (sibling of vector-bindings/) build.rs walks for
  API auto-discovery - its own Cargo.toml carries the version
- the `timberio/vector` Docker tag the test suite's vector_runner fixture
  pulls (vectordotdev/tests/conftest.py's _VECTOR_TAG)

vectordotdev/vector tags two independent things under one repo: product
releases (v0.58.0, no hyphen) and its own vdev build-tool releases
(vdev-v0.3.16) - `git ls-remote` returns both, and only the first is what
"latest Vector" means here.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from common import log_message

REPO_ROOT = Path(__file__).resolve().parent.parent
VECTOR_DIR = REPO_ROOT / "vector"
CONFTEST_PATH = REPO_ROOT / "vectordotdev" / "tests" / "conftest.py"
VECTOR_TAG_RE = re.compile(r'^v\d+\.\d+\.\d+$')


def latest_vector_version() -> str:
    """Latest real Vector product tag (e.g. "v0.58.0"), never a vdev-* one."""
    result = subprocess.run(
        ["git", "ls-remote", "--tags", "--refs",
         "https://github.com/vectordotdev/vector.git"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    tags = (line.rsplit("refs/tags/", 1)[-1] for line in result.stdout.splitlines())
    versions = [t for t in tags if VECTOR_TAG_RE.match(t)]
    if not versions:
        raise RuntimeError("no vX.Y.Z tags found on vectordotdev/vector - check the filter")
    versions.sort(key=lambda v: tuple(int(p) for p in v[1:].split(".")), reverse=True)
    return versions[0]


def current_checkout_version() -> str | None:
    cargo_toml = VECTOR_DIR / "Cargo.toml"
    if not cargo_toml.exists():
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', cargo_toml.read_text(), re.MULTILINE)
    return f"v{match.group(1)}" if match else None


def current_docker_tag() -> str | None:
    match = re.search(r'_VECTOR_TAG = "([^"]+)"', CONFTEST_PATH.read_text())
    return match.group(1) if match else None


def check() -> None:
    latest = latest_vector_version()
    checkout = current_checkout_version()
    docker_tag = current_docker_tag()
    docker_version = f"v{docker_tag.removesuffix('-debian')}" if docker_tag else None

    stale = []
    if checkout is not None and checkout != latest:
        stale.append(f"vector/ checkout is {checkout}, latest is {latest}")
    if docker_version is not None and docker_version != latest:
        stale.append(f"test Docker image is {docker_tag}, latest is {latest}-debian")

    if not stale:
        log_message(f"Vector pin is current: {latest}")
        return

    for line in stale:
        print(f"::warning::{line} - run `python3 build/vector_pin.py update`", file=sys.stderr)
        log_message(f"stale: {line}")


def update() -> None:
    latest = latest_vector_version()
    new_tag = f"{latest.removeprefix('v')}-debian"

    conftest_src = CONFTEST_PATH.read_text()
    new_src = re.sub(r'_VECTOR_TAG = "[^"]+"', f'_VECTOR_TAG = "{new_tag}"', conftest_src)
    if new_src == conftest_src:
        log_message(f"conftest.py already pins {new_tag}")
    else:
        CONFTEST_PATH.write_text(new_src)
        log_message(f"conftest.py -> {new_tag}")

    if (VECTOR_DIR / ".git").exists():
        # A real clone - cwd=VECTOR_DIR is safe, git won't walk up to the
        # repo root's .git looking for one.
        subprocess.run(["git", "fetch", "--depth", "1", "origin", "tag", latest],
                        cwd=VECTOR_DIR, check=True)
        subprocess.run(["git", "checkout", latest], cwd=VECTOR_DIR, check=True)
        log_message(f"vector/ checked out at {latest}")
    elif VECTOR_DIR.exists():
        # A plain directory with no .git of its own (a raw source copy,
        # not a clone) - `git` commands with this as cwd would silently
        # walk up and operate on the OUTER repo instead. Remove it by hand
        # first; this script won't delete a directory it doesn't own.
        print(f"vector/ exists but is not a git clone (no vector/.git) - "
              f"remove it yourself, then rerun: rm -rf {VECTOR_DIR}", file=sys.stderr)
        raise SystemExit(1)
    else:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", latest,
             "https://github.com/vectordotdev/vector.git", str(VECTOR_DIR)],
            check=True,
        )
        log_message(f"vector/ cloned at {latest}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "update"])
    args = parser.parse_args()

    if args.action == "check":
        check()
    else:
        update()
    return 0


if __name__ == "__main__":
    sys.exit(main())
