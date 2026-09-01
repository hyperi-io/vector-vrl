"""Pre-provisioned production patterns for common log formats.

Optimized for native Vector execution with 350+ THG performance
Loads patterns from YAML configuration files
"""

from pathlib import Path
from typing import Any

import yaml

# The patterns with a YAML config under patterns/configs/ - the only names
# get_pattern and benchmark_all_patterns accept.
_PATTERN_NAMES = (
    "apache_combined",
    "nginx_access",
    "json_application",
    "kubernetes_pods",
    "docker_container",
)


def _remap_source(config: dict[str, Any]) -> str:
    """The VRL of the config's single ``remap`` transform."""
    remaps = {
        name: transform
        for name, transform in config.get("transforms", {}).items()
        if transform.get("type") == "remap"
    }
    if len(remaps) != 1:
        raise ValueError(f"expected exactly one remap transform, found {len(remaps)}")
    ((name, transform),) = remaps.items()
    source = transform.get("source")
    if source is None:
        raise ValueError(f"remap transform {name!r} has no inline source")
    return source


class ProductionPatterns:
    """Library of production-ready Vector configurations loaded from YAML files.

    All patterns optimized for native in-process execution with high THG scores
    """

    def __init__(self):
        """Set up the patterns directory and an empty pattern cache."""
        self.patterns_dir = Path(__file__).parent / "patterns" / "configs"
        self.pattern_cache = {}

    def _load_yaml_config(self, pattern_name: str) -> dict[str, Any]:
        """Load Vector configuration from YAML file."""
        if pattern_name in self.pattern_cache:
            return self.pattern_cache[pattern_name]

        yaml_file = self.patterns_dir / f"{pattern_name}.yaml"
        if not yaml_file.exists():
            raise FileNotFoundError(f"Pattern not found: {pattern_name} ({yaml_file})")

        try:
            with open(yaml_file) as f:
                config = yaml.safe_load(f)
                self.pattern_cache[pattern_name] = config
                return config
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {pattern_name}: {e}")

    def get_apache_combined(self) -> dict[str, Any]:
        """Apache Combined Log Format from YAML config.

        Expected THG: 350+ EPS with full field extraction (10 fields)
        """
        return self._load_yaml_config("apache_combined")

    def get_nginx_access(self) -> dict[str, Any]:
        """Nginx Access Log Format from YAML config.

        Expected THG: 400+ EPS with 9 field extraction
        """
        return self._load_yaml_config("nginx_access")

    def get_json_application(self) -> dict[str, Any]:
        """JSON Application Logs from YAML config (highest performance).

        Expected THG: 500+ EPS using parse_json built-in
        """
        return self._load_yaml_config("json_application")

    def get_kubernetes_pods(self) -> dict[str, Any]:
        """Kubernetes Pod Logs from YAML config.

        Expected THG: 300+ EPS with K8s metadata extraction
        """
        return self._load_yaml_config("kubernetes_pods")

    def get_docker_container(self) -> dict[str, Any]:
        """Docker Container Logs from YAML config.

        Expected THG: 400+ EPS with optimized container parsing
        """
        return self._load_yaml_config("docker_container")

    @staticmethod
    def list_available_patterns() -> list[str]:
        """Get list of all available production patterns."""
        return list(_PATTERN_NAMES)

    @staticmethod
    def get_pattern(pattern_name: str) -> dict[str, Any]:
        """Get production pattern by name, through the module-level instance's cache."""
        if pattern_name not in _PATTERN_NAMES:
            raise ValueError(
                f"Unknown pattern: {pattern_name}. Available: {list(_PATTERN_NAMES)}"
            )
        return production_patterns._load_yaml_config(pattern_name)

    @staticmethod
    def benchmark_all_patterns(test_data_sets: dict[str, list[str]]) -> dict[str, dict]:
        """Benchmark all production patterns with their respective test data.

        Returns THG scores for comparative analysis
        """
        import vector_vrl

        results = {}
        for pattern_name in ProductionPatterns.list_available_patterns():
            if pattern_name not in test_data_sets:
                continue

            try:
                config = ProductionPatterns.get_pattern(pattern_name)
                vrl_code = _remap_source(config)
                test_data = test_data_sets[pattern_name]

                thg_result = vector_vrl.assess_vrl_performance(
                    vrl_code, test_data, pattern_name
                )
                results[pattern_name] = thg_result

            except Exception as e:
                results[pattern_name] = {"error": str(e), "thg_score": 0}

        return results


# Convenience exports for easy access
production_patterns = ProductionPatterns()


# Direct pattern access (instance methods)
def get_apache_combined():
    """Return the Apache Combined Log Format pattern."""
    return production_patterns.get_apache_combined()


def get_nginx_access():
    """Return the Nginx Access Log Format pattern."""
    return production_patterns.get_nginx_access()


def get_json_application():
    """Return the JSON Application Logs pattern."""
    return production_patterns.get_json_application()


def get_kubernetes_pods():
    """Return the Kubernetes Pod Logs pattern."""
    return production_patterns.get_kubernetes_pods()


def get_docker_container():
    """Return the Docker Container Logs pattern."""
    return production_patterns.get_docker_container()
