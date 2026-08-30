#!/usr/bin/env python3
"""Vector version auto-detection with web fetch.

Automatically detects the latest compatible Vector version from GitHub API.
"""

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class VectorVersionDetector:
    """Auto-detect Vector versions from GitHub API."""

    def __init__(self, config_file: str | None = None):
        """Load Vector version detection settings from the environment and optional config file."""
        # Configuration from environment or config file (NO hardcoded values)
        self.github_api_url = os.getenv(
            "VECTORDOTDEV_GITHUB_API_URL",
            "https://api.github.com/repos/vectordotdev/vector/releases",
        )
        self.fallback_count = int(os.getenv("VECTORDOTDEV_FALLBACK_COUNT", "3"))
        self.min_version = os.getenv("VECTORDOTDEV_MIN_VERSION")  # No default
        self.max_version = os.getenv("VECTORDOTDEV_MAX_VERSION")  # No default
        self.timeout = int(os.getenv("VECTORDOTDEV_VERSION_TIMEOUT", "10"))

        # Load additional config if provided
        if config_file and os.path.exists(config_file):
            self._load_config_file(config_file)

    def _load_config_file(self, config_file: str):
        """Load configuration from file."""
        try:
            import toml

            with open(config_file) as f:
                config = toml.load(f)

            vector_config = config.get("vector_integration", {})

            # Update settings from config file (override defaults, not hardcode)
            if "github_api_url" in vector_config:
                self.github_api_url = vector_config["github_api_url"]
            if "auto_detect_fallback_count" in vector_config:
                self.fallback_count = vector_config["auto_detect_fallback_count"]

        except Exception as e:
            print(f"Warning: Could not load config file {config_file}: {e}")

    def fetch_vector_releases(self) -> list[dict[str, Any]]:
        """Fetch Vector releases from GitHub API."""
        try:
            print("Fetching Vector releases from GitHub API...")
            with urlopen(self.github_api_url, timeout=self.timeout) as response:
                data = json.loads(response.read())

            # Filter to stable releases (not pre-releases)
            stable_releases = [
                release
                for release in data
                if not release.get("prerelease", True)
                and not release.get("draft", True)
            ]

            print(f"Found {len(stable_releases)} stable Vector releases")
            return stable_releases

        except HTTPError as e:
            print(f"GitHub API error: {e}")
            return []
        except URLError as e:
            print(f"Network error: {e}")
            return []
        except Exception as e:
            print(f"Fetch error: {e}")
            return []

    def get_compatible_versions(self, count: int | None = None) -> list[str]:
        """Get list of compatible Vector versions."""
        releases = self.fetch_vector_releases()
        if not releases:
            print("No releases found")
            return []

        # Extract version tags (filter out dev/rc versions)
        versions = []
        for release in releases:
            tag = release.get("tag_name", "")
            if tag.startswith("v") and not any(
                x in tag.lower() for x in ["dev", "rc", "alpha", "beta"]
            ):
                version = tag[1:]  # Remove 'v' prefix

                # Must be semantic version (x.y.z)
                if self._is_semantic_version(version):
                    # Apply version constraints if configured
                    if self._is_version_compatible(version):
                        versions.append(tag)

        # Return requested count (default from config)
        max_count = count or self.fallback_count
        return versions[:max_count]

    def _is_semantic_version(self, version: str) -> bool:
        """Check if version follows semantic versioning (x.y.z)."""
        try:
            parts = version.split(".")
            return (
                len(parts) >= 2
                and all(part.isdigit() for part in parts[:3])
                and int(parts[0]) >= 0
                and int(parts[1]) >= 0
            )
        except (ValueError, IndexError):
            return False

    def _is_version_compatible(self, version: str) -> bool:
        """Check if version meets compatibility constraints."""
        # Skip constraint checking if not configured
        if not self.min_version and not self.max_version:
            return True

        try:
            # Simple version comparison (major.minor.patch)
            version_parts = [int(x) for x in version.split(".")]

            if self.min_version:
                min_parts = [int(x) for x in self.min_version.split(".")]
                if version_parts < min_parts:
                    return False

            if self.max_version:
                max_parts = [int(x) for x in self.max_version.split(".")]
                if version_parts > max_parts:
                    return False

            return True

        except (ValueError, IndexError):
            # If version parsing fails, allow it (conservative approach)
            return True

    def get_latest_compatible_version(self) -> str | None:
        """Get the latest compatible Vector version."""
        versions = self.get_compatible_versions(count=1)
        return versions[0] if versions else None

    def detect_current_project_version(self) -> str | None:
        """Detect current Vector version used in project."""
        # Check environment variable first
        if "VECTORDOTDEV_VECTOR_VERSION" in os.environ:
            return os.environ["VECTORDOTDEV_VECTOR_VERSION"]

        # Check Cargo.toml files for Vector version
        toml_files = ["../vector-bindings/Cargo.toml", "./Cargo.toml"]

        for toml_file in toml_files:
            if os.path.exists(toml_file):
                try:
                    with open(toml_file) as f:
                        content = f.read()
                        # Look for Vector git tag
                        if 'tag = "v' in content:
                            import re

                            match = re.search(r'tag = "v([^"]+)"', content)
                            if match:
                                return f"v{match.group(1)}"
                except Exception:
                    continue

        return None


def main():
    """CLI for Vector version detection."""
    import argparse

    parser = argparse.ArgumentParser(description="Vector version auto-detection")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--count", type=int, help="Number of versions to fetch")
    parser.add_argument("--latest", action="store_true", help="Get latest version only")
    parser.add_argument(
        "--current", action="store_true", help="Detect current project version"
    )

    args = parser.parse_args()

    detector = VectorVersionDetector(config_file=args.config)

    if args.current:
        current = detector.detect_current_project_version()
        print(f"Current project Vector version: {current or 'Not detected'}")
    elif args.latest:
        latest = detector.get_latest_compatible_version()
        print(f"Latest compatible Vector version: {latest or 'Not found'}")
    else:
        versions = detector.get_compatible_versions(count=args.count)
        print(f"Compatible Vector versions: {versions}")


if __name__ == "__main__":
    main()
