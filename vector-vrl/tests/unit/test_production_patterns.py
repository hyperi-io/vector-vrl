"""`ProductionPatterns.get_pattern` hands back a loaded pattern config.

It mapped the getters off the class rather than an instance, so every call
raised TypeError for want of `self` - and nothing called it until now.
"""

import pytest

pytest.importorskip("yaml")

from vector_vrl.production_patterns import (  # noqa: E402
    ProductionPatterns,
    _remap_source,
    get_apache_combined,
    get_docker_container,
    get_json_application,
    get_kubernetes_pods,
    get_nginx_access,
    production_patterns,
)

NAMED_PATTERNS = ProductionPatterns.list_available_patterns()

MODULE_GETTERS = {
    "apache_combined": get_apache_combined,
    "nginx_access": get_nginx_access,
    "json_application": get_json_application,
    "kubernetes_pods": get_kubernetes_pods,
    "docker_container": get_docker_container,
}


@pytest.mark.parametrize("name", NAMED_PATTERNS)
def test_module_level_getter_returns_the_named_pattern(name):
    assert MODULE_GETTERS[name]() == ProductionPatterns.get_pattern(name)


def test_the_module_instance_caches_each_pattern():
    first = production_patterns.get_apache_combined()

    assert production_patterns.get_apache_combined() is first


def test_a_pattern_without_a_config_file_is_reported(tmp_path):
    patterns = ProductionPatterns()
    patterns.patterns_dir = tmp_path

    with pytest.raises(FileNotFoundError, match="apache_combined"):
        patterns.get_apache_combined()


def test_invalid_yaml_is_reported_as_a_value_error(tmp_path):
    (tmp_path / "nginx_access.yaml").write_text("a: [", encoding="utf-8")
    patterns = ProductionPatterns()
    patterns.patterns_dir = tmp_path

    with pytest.raises(ValueError, match="Invalid YAML in nginx_access"):
        patterns.get_nginx_access()


def test_every_advertised_pattern_has_a_config_file():
    """`list_available_patterns` once named three patterns with no YAML."""
    assert NAMED_PATTERNS == [
        "apache_combined",
        "nginx_access",
        "json_application",
        "kubernetes_pods",
        "docker_container",
    ]


@pytest.mark.parametrize("name", NAMED_PATTERNS)
def test_get_pattern_returns_the_loaded_config(name):
    config = ProductionPatterns.get_pattern(name)

    assert isinstance(config, dict)
    assert "transforms" in config


def test_get_pattern_rejects_an_unknown_name():
    with pytest.raises(ValueError, match="Unknown pattern"):
        ProductionPatterns.get_pattern("no_such_pattern")


@pytest.mark.parametrize("name", NAMED_PATTERNS)
def test_every_named_pattern_has_one_remap_transform(name):
    source = _remap_source(ProductionPatterns.get_pattern(name))

    assert isinstance(source, str)
    assert source.strip()


def test_remap_source_refuses_a_remap_without_inline_source():
    with pytest.raises(ValueError, match="'t' has no inline source"):
        _remap_source({"transforms": {"t": {"type": "remap", "file": "x.vrl"}}})


def test_remap_source_refuses_a_config_without_exactly_one_remap():
    with pytest.raises(ValueError, match="found 0"):
        _remap_source({"transforms": {"t": {"type": "filter"}}})
    with pytest.raises(ValueError, match="found 2"):
        _remap_source(
            {
                "transforms": {
                    "a": {"type": "remap", "source": ".x = 1"},
                    "b": {"type": "remap", "source": ".y = 2"},
                }
            }
        )
