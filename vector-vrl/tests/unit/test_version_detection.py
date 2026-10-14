"""Config-file loading in `version_detection`.

The loader used to import the third-party `toml` package, which this
package never declares, so every config file was silently ignored behind a
printed warning. It reads with the stdlib `tomllib` now; these pin that.
"""

from vector_vrl.version_detection import VectorVersionDetector


def test_config_file_overrides_the_env_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("VECTOR_VRL_GITHUB_API_URL", raising=False)
    monkeypatch.delenv("VECTOR_VRL_FALLBACK_COUNT", raising=False)
    config = tmp_path / "settings.toml"
    config.write_text(
        "[vector_integration]\n"
        'github_api_url = "https://example.invalid/releases"\n'
        "auto_detect_fallback_count = 7\n",
        encoding="utf-8",
    )

    detector = VectorVersionDetector(config_file=str(config))

    assert detector.github_api_url == "https://example.invalid/releases"
    assert detector.fallback_count == 7


def test_a_missing_config_file_keeps_the_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("VECTOR_VRL_GITHUB_API_URL", raising=False)
    monkeypatch.delenv("VECTOR_VRL_FALLBACK_COUNT", raising=False)

    detector = VectorVersionDetector(config_file=str(tmp_path / "absent.toml"))

    assert detector.github_api_url.startswith("https://api.github.com/")
    assert detector.fallback_count == 3


def test_a_malformed_config_file_is_reported_not_fatal(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("VECTOR_VRL_GITHUB_API_URL", raising=False)
    monkeypatch.delenv("VECTOR_VRL_FALLBACK_COUNT", raising=False)
    config = tmp_path / "broken.toml"
    config.write_text("[vector_integration\n", encoding="utf-8")

    detector = VectorVersionDetector(config_file=str(config))

    assert detector.fallback_count == 3
    assert "Could not load config file" in capsys.readouterr().out


def test_a_file_url_is_refused_before_it_is_opened(tmp_path, monkeypatch, capsys):
    secret = tmp_path / "releases.json"
    secret.write_text(
        '[{"tag_name": "v9.9.9", "prerelease": false, "draft": false}]',
        encoding="utf-8",
    )
    monkeypatch.setenv("VECTOR_VRL_GITHUB_API_URL", secret.as_uri())

    detector = VectorVersionDetector()

    assert detector.fetch_vector_releases() == []
    assert "not https" in capsys.readouterr().out
