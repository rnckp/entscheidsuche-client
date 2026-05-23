"""
Configuration loading for entscheidsuche client defaults.
"""

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class EntscheidsucheConfig:
    """Runtime settings loaded from config.yaml when available."""

    base_url: str = "https://entscheidsuche.ch"
    docs_url: str = "https://entscheidsuche.ch/docs"
    search_url: str = "https://entscheidsuche.ch/_search.php"
    timeout: float = 30.0
    rate_limit_delay: float = 0.5
    default_search_size: int = 10
    default_sort_order: str = "desc"
    default_download_formats: tuple[str, ...] = ("json", "html", "pdf")
    default_date_output_format: str = "%d.%m.%Y"


DEFAULT_CONFIG = EntscheidsucheConfig()


def load_config(config_path: Path | str | None = None) -> EntscheidsucheConfig:
    """
    Load runtime settings from config.yaml.

    Missing config files are treated as an instruction to use the package defaults,
    which keeps library usage predictable outside this repository.
    """
    path = Path(config_path) if config_path is not None else Path("config.yaml")
    if not path.exists():
        return DEFAULT_CONFIG

    with path.open(encoding="utf-8") as config_file:
        raw_config = yaml.safe_load(config_file) or {}

    if not isinstance(raw_config, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")

    section = raw_config.get("entscheidsuche", raw_config)
    if not isinstance(section, dict):
        raise ValueError("The 'entscheidsuche' config section must be a mapping")

    defaults = DEFAULT_CONFIG.__dict__.copy()
    allowed_keys = {field.name for field in fields(EntscheidsucheConfig)}
    unknown_keys = sorted(set(section) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"Unknown config keys: {', '.join(unknown_keys)}")

    values: dict[str, Any] = defaults | section
    values["timeout"] = float(values["timeout"])
    values["rate_limit_delay"] = float(values["rate_limit_delay"])
    values["default_search_size"] = int(values["default_search_size"])
    values["default_download_formats"] = tuple(values["default_download_formats"])
    return EntscheidsucheConfig(**values)
