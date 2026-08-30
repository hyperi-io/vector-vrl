"""Check and update the Vector version this repo builds and tests against.

One pin: the `timberio/vector` Docker tag the test suite's vector_runner
fixture pulls (vector-vrl/tests/conftest.py's _VECTOR_TAG). `vector-bindings`
itself reads no local Vector checkout, so there is nothing else to pin here.

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
CONFTEST_PATH = REPO_ROOT / "vector-vrl" / "tests" / "conftest.py"
VECTOR_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
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
        ["git", "ls-remote", "--tags", "https://github.com/vectordotdev/vector.git"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    commit_sha_by_tag: dict[str, str] = {}
    for line in result.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        ref = ref.removesuffix("^{}")
        tag = ref.rsplit("refs/tags/", 1)[-1]
        if VECTOR_TAG_RE.match(tag):
            commit_sha_by_tag[tag] = sha
    if not commit_sha_by_tag:
        raise RuntimeError(
            "no vX.Y.Z tags found on vectordotdev/vector - check the filter"
        )
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
        log_message(
            f"{tag} is only {age_days:.1f}d old - within the {COOLDOWN_DAYS}d cooldown, skipping"
        )
    return None


def _version_tuple(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.removeprefix("v").split("."))


def current_docker_tag() -> str | None:
    """The `_VECTOR_TAG` value conftest.py's vector_runner fixture currently pins."""
    match = re.search(r'_VECTOR_TAG = "([^"]+)"', CONFTEST_PATH.read_text())
    return match.group(1) if match else None


def check() -> None:
    """Warn (never fail) if the Docker pin is behind the cooldown-cleared latest."""
    latest = latest_vector_version()
    if latest is None:
        log_message(
            f"no Vector release has cleared the {COOLDOWN_DAYS}-day cooldown yet"
        )
        return

    docker_tag = current_docker_tag()
    docker_version = f"v{docker_tag.removesuffix('-debian')}" if docker_tag else None

    if docker_version is not None and _version_tuple(docker_version) < _version_tuple(
        latest
    ):
        line = f"test Docker image is {docker_tag}, latest is {latest}-debian"
        print(
            f"::warning::{line} - run `python3 build/vector_pin.py update`",
            file=sys.stderr,
        )
        log_message(f"stale: {line}")
        return

    log_message(f"Vector pin is current: {latest}")


def update() -> None:
    """Bump the Docker pin to the cooldown-cleared latest, if it is behind it."""
    latest = latest_vector_version()
    if latest is None:
        log_message(
            f"no Vector release has cleared the {COOLDOWN_DAYS}-day cooldown yet - nothing to do"
        )
        return

    docker_tag = current_docker_tag()
    docker_version = f"v{docker_tag.removesuffix('-debian')}" if docker_tag else None
    if docker_version is not None and _version_tuple(docker_version) >= _version_tuple(
        latest
    ):
        log_message(
            f"already at {docker_tag}, >= cooldown-cleared {latest} - nothing to do"
        )
        return

    new_tag = f"{latest.removeprefix('v')}-debian"

    conftest_src = CONFTEST_PATH.read_text()
    new_src = re.sub(
        r'_VECTOR_TAG = "[^"]+"', f'_VECTOR_TAG = "{new_tag}"', conftest_src
    )
    if new_src == conftest_src:
        log_message(f"conftest.py already pins {new_tag}")
    else:
        CONFTEST_PATH.write_text(new_src)
        log_message(f"conftest.py -> {new_tag}")


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
