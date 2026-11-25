"""Check and update the Vector version this repo builds and tests against.

One pin: the `timberio/vector` Docker image the test suite's vector_runner
fixture pulls, as a tag plus the digest of that tag's multi-arch index
(vector-vrl/tests/conftest.py's _VECTOR_TAG and _VECTOR_DIGEST). `vector-bindings`
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
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from common import log_message

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFTEST_PATH = REPO_ROOT / "vector-vrl" / "tests" / "conftest.py"
VECTOR_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
COOLDOWN_DAYS = 7
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DOCKER_AUTH_URL = (
    "https://auth.docker.io/token?service=registry.docker.io"
    "&scope=repository:timberio/vector:pull"
)
DOCKER_MANIFEST_URL = "https://registry-1.docker.io/v2/timberio/vector/manifests/{tag}"
INDEX_ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
    ]
)


def _tags_newest_first() -> list[str]:
    """Real product tags, newest version first.

    `git ls-remote` also lists a `^{}`-suffixed peeled line for each annotated
    tag, so the set removes the duplicate.
    """
    result = subprocess.run(
        ["git", "ls-remote", "--tags", "https://github.com/vectordotdev/vector.git"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=True,
    )
    tags = {
        ref.removesuffix("^{}").rsplit("refs/tags/", 1)[-1]
        for _, _, ref in (line.partition("\t") for line in result.stdout.splitlines())
    }
    product_tags = [tag for tag in tags if VECTOR_TAG_RE.match(tag)]
    if not product_tags:
        raise RuntimeError(
            "no vX.Y.Z tags found on vectordotdev/vector - check the filter"
        )
    return sorted(product_tags, key=_version_tuple, reverse=True)


def _release_published_at(tag: str) -> str | None:
    """When the GitHub release for `tag` was published, or None if it has none.

    The release date, not the tagged commit's: a release cut from an older
    commit is as fresh as its publication.
    """
    url = f"https://api.github.com/repos/vectordotdev/vector/releases/tags/{tag}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        # The URL is a fixed https:// prefix plus a tag VECTOR_TAG_RE matched.
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    return data.get("published_at")


def first_cleared_release(
    published: list[tuple[str, str | None]], now: datetime
) -> str | None:
    """The first `(tag, published_at)` published at least COOLDOWN_DAYS before `now`.

    A tag with no published release is skipped, never adopted on its commit date.
    """
    for tag, published_at in published:
        if published_at is None:
            log_message(f"{tag} has no published GitHub release - skipping")
            continue
        released = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_days = (now - released).total_seconds() / 86400
        if age_days >= COOLDOWN_DAYS:
            return tag
        log_message(
            f"{tag} was released {age_days:.1f}d ago - within the {COOLDOWN_DAYS}d cooldown, skipping"
        )
    return None


def latest_vector_version() -> str | None:
    """Newest Vector product release that has cleared the 7-day cooldown.

    None if every release newer than the current pin is still too fresh -
    that's a normal, expected outcome on most days, not an error.
    """
    now = datetime.now(UTC)
    for tag in _tags_newest_first():
        cleared = first_cleared_release([(tag, _release_published_at(tag))], now)
        if cleared is not None:
            return cleared
    return None


def _version_tuple(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.removeprefix("v").split("."))


def current_docker_tag() -> str | None:
    """The `_VECTOR_TAG` value conftest.py's vector_runner fixture currently pins."""
    match = re.search(r'_VECTOR_TAG = "([^"]+)"', CONFTEST_PATH.read_text())
    return match.group(1) if match else None


def current_docker_digest() -> str | None:
    """The `_VECTOR_DIGEST` value conftest.py currently pins."""
    match = re.search(r'_VECTOR_DIGEST = \(?\s*"([^"]+)"', CONFTEST_PATH.read_text())
    return match.group(1) if match else None


def docker_index_digest(tag: str) -> str:
    """The `sha256:` digest of the multi-arch index Docker Hub serves for `tag`.

    Anonymous: a pull-scope token from auth.docker.io, no login. The digest is
    the hash of the index bytes, so it is computed from the body and not taken
    from a header. A tag that resolves to a single-platform manifest is an error,
    because a digest of one architecture would break the other runner.
    """
    # Fixed https:// URLs, the tag matched VECTOR_TAG_RE upstream of this call.
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    with urllib.request.urlopen(DOCKER_AUTH_URL, timeout=30) as resp:  # noqa: S310
        token = json.load(resp)["token"]
    req = urllib.request.Request(  # noqa: S310
        DOCKER_MANIFEST_URL.format(tag=tag),
        headers={"Authorization": f"Bearer {token}", "Accept": INDEX_ACCEPT},
    )
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = resp.read()
    if not json.loads(body).get("manifests"):
        raise RuntimeError(f"timberio/vector:{tag} is not a multi-arch index")
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


def pin_image(src: str, tag: str, digest: str) -> str:
    """`src` with `_VECTOR_TAG` and `_VECTOR_DIGEST` set to `tag` and `digest`.

    Raises ValueError for a digest that isn't `sha256:` plus 64 hex characters,
    and for a source missing either assignment, so a bad write never lands.
    """
    if not DIGEST_RE.match(digest):
        raise ValueError(f"not a sha256 digest: {digest!r}")
    for name, value in (("_VECTOR_TAG", tag), ("_VECTOR_DIGEST", digest)):
        # ruff format wraps the long digest line in parentheses.
        src, count = re.subn(rf'({name} = \(?\s*)"[^"]*"', rf'\g<1>"{value}"', src)
        if count != 1:
            raise ValueError(f"expected one {name} assignment, found {count}")
    return src


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
    current = docker_version is not None and _version_tuple(
        docker_version
    ) >= _version_tuple(latest)
    if current and current_docker_digest() is not None:
        log_message(
            f"already at {docker_tag}, >= cooldown-cleared {latest} - nothing to do"
        )
        return

    if current and docker_tag is not None:
        new_tag = docker_tag
    else:
        new_tag = f"{latest.removeprefix('v')}-debian"
    digest = docker_index_digest(new_tag)

    conftest_src = CONFTEST_PATH.read_text()
    new_src = pin_image(conftest_src, new_tag, digest)
    if new_src == conftest_src:
        log_message(f"conftest.py already pins {new_tag}@{digest}")
    else:
        CONFTEST_PATH.write_text(new_src)
        log_message(f"conftest.py -> {new_tag}@{digest}")


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
