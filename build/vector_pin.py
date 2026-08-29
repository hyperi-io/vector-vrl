"""Check and update the Vector version this repo builds and tests against.

Two independent pins:
- the `vector/` checkout (sibling of vector-bindings/) build.rs walks for
  API auto-discovery - its own Cargo.toml carries the version
- the `timberio/vector` Docker tag the test suite's vector_runner fixture
  pulls (vectordotdev/tests/conftest.py's _VECTOR_TAG)

vectordotdev/vector tags two independent things under one repo: product
releases (v0.58.0, no hyphen) and its own vdev build-tool releases
(vdev-v0.3.16) - `git ls-remote` returns both, and only the first is what
"latest Vector" means here.

7-day release-age cooldown (HyperI supply-chain policy, external deps):
never adopt a Vector release published less than 7 days ago, even if it
is the newest tag - a fresh release is exactly the one nobody has run
against yet.
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from common import log_message

REPO_ROOT = Path(__file__).resolve().parent.parent
VECTOR_DIR = REPO_ROOT / "vector"
CONFTEST_PATH = REPO_ROOT / "vectordotdev" / "tests" / "conftest.py"
VECTOR_TAG_RE = re.compile(r'^v\d+\.\d+\.\d+$')
COOLDOWN_DAYS = 7


def _tags_newest_first() -> list[tuple[str, str]]:
    """[(tag, commit_sha), ...] for real product tags, newest version first.

    An annotated tag's own ref SHA points at the TAG OBJECT, not the
    commit - the GitHub commits API 422s on that. `git ls-remote` without
    `--refs` also emits a `^{}`-suffixed "peeled" line carrying the actual
    commit SHA for each annotated tag; that line, when present, replaces
    the plain one. A lightweight tag has no peeled line and its ref SHA
    already is the commit SHA.
    """
    result = subprocess.run(
        ["git", "ls-remote", "--tags",
         "https://github.com/vectordotdev/vector.git"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    commit_sha_by_tag: dict[str, str] = {}
    for line in result.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        ref = ref.removesuffix("^{}")
        tag = ref.rsplit("refs/tags/", 1)[-1]
        if VECTOR_TAG_RE.match(tag):
            commit_sha_by_tag[tag] = sha
    if not commit_sha_by_tag:
        raise RuntimeError("no vX.Y.Z tags found on vectordotdev/vector - check the filter")
    pairs = list(commit_sha_by_tag.items())
    pairs.sort(key=lambda p: tuple(int(x) for x in p[0][1:].split(".")), reverse=True)
    return pairs


def _commit_age_days(sha: str) -> float:
    """Age in days of a commit, via the public (unauthenticated) GitHub API."""
    url = f"https://api.github.com/repos/vectordotdev/vector/commits/{sha}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    date_str = data["commit"]["committer"]["date"]  # e.g. "2026-08-20T10:00:00Z"
    committed_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return (datetime.now(UTC) - committed_at).total_seconds() / 86400


def latest_vector_version() -> str | None:
    """Newest Vector product tag that has cleared the 7-day cooldown.

    None if every release newer than the current pin is still too fresh -
    that's a normal, expected outcome on most days, not an error.
    """
    for tag, sha in _tags_newest_first():
        age_days = _commit_age_days(sha)
        if age_days >= COOLDOWN_DAYS:
            return tag
        log_message(f"{tag} is only {age_days:.1f}d old - within the {COOLDOWN_DAYS}d cooldown, skipping")
    return None


def _version_tuple(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.removeprefix("v").split("."))


def current_checkout_version() -> str | None:
    """Version the local vector/ checkout's own Cargo.toml declares, if present."""
    cargo_toml = VECTOR_DIR / "Cargo.toml"
    if not cargo_toml.exists():
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', cargo_toml.read_text(), re.MULTILINE)
    return f"v{match.group(1)}" if match else None


def current_docker_tag() -> str | None:
    """The `_VECTOR_TAG` value conftest.py's vector_runner fixture currently pins."""
    match = re.search(r'_VECTOR_TAG = "([^"]+)"', CONFTEST_PATH.read_text())
    return match.group(1) if match else None


def check() -> None:
    """Warn (never fail) if either pin is behind the cooldown-cleared latest."""
    latest = latest_vector_version()
    if latest is None:
        log_message(f"no Vector release has cleared the {COOLDOWN_DAYS}-day cooldown yet")
        return

    checkout = current_checkout_version()
    docker_tag = current_docker_tag()
    docker_version = f"v{docker_tag.removesuffix('-debian')}" if docker_tag else None

    stale = []
    if checkout is not None and _version_tuple(checkout) < _version_tuple(latest):
        stale.append(f"vector/ checkout is {checkout}, latest is {latest}")
    if docker_version is not None and _version_tuple(docker_version) < _version_tuple(latest):
        stale.append(f"test Docker image is {docker_tag}, latest is {latest}-debian")

    if not stale:
        log_message(f"Vector pin is current: {latest}")
        return

    for line in stale:
        print(f"::warning::{line} - run `python3 build/vector_pin.py update`", file=sys.stderr)
        log_message(f"stale: {line}")


def update() -> None:
    """Bump both pins to the cooldown-cleared latest, if either is behind it."""
    latest = latest_vector_version()
    if latest is None:
        log_message(f"no Vector release has cleared the {COOLDOWN_DAYS}-day cooldown yet - nothing to do")
        return

    current = current_checkout_version()
    if current is not None and _version_tuple(current) >= _version_tuple(latest):
        log_message(f"already at {current}, >= cooldown-cleared {latest} - nothing to do")
        return

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
    """CLI entry point - `check` or `update`."""
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
