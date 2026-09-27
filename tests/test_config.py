"""Validation of local runtime configuration."""

from pathlib import Path

import pytest

from entscheidsuche.config import DEFAULT_CONFIG, load_config


@pytest.mark.parametrize(
    "setting",
    [
        "timeout: -1",
        "timeout: .nan",
        "timeout: .inf",
        "timeout: true",
        "rate_limit_delay: -1",
        "default_search_size: 1.5",
        "default_search_size: 10001",
        "default_search_size: true",
        "default_sort_order: backwards",
        "default_download_formats: pdf",
        "default_download_formats: [exe]",
        "docs_url: file:///tmp/docs",
        "base_url: https://user:password@example.org",
    ],
)
def test_invalid_config_is_rejected(tmp_path: Path, setting: str) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(setting, encoding="utf-8")
    with pytest.raises((TypeError, ValueError)):
        load_config(path)


@pytest.mark.parametrize("contents", ["[]", "false", "0", "entscheidsuche: []"])
def test_non_mapping_config_is_rejected(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises((TypeError, ValueError)):
        load_config(path)


def test_explicit_missing_config_is_not_silently_ignored(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.yaml")


def test_implicit_missing_config_uses_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_config() == DEFAULT_CONFIG


def test_valid_config_overrides_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "entscheidsuche:\n  timeout: 12\n  default_download_formats: [pdf]\n", encoding="utf-8"
    )
    config = load_config(path)
    assert config.timeout == 12
    assert config.default_download_formats == ("pdf",)
    assert config.search_url == DEFAULT_CONFIG.search_url
