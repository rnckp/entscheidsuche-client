"""Validated runtime configuration for the client."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator


class EntscheidsucheConfig(BaseModel):
    """Runtime settings loaded from config.yaml when available."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, hide_input_in_errors=True)

    base_url: str = "https://entscheidsuche.ch"
    docs_url: str = "https://entscheidsuche.ch/docs"
    search_url: str = "https://entscheidsuche.ch/_search.php"
    timeout: float = Field(default=30.0, gt=0, allow_inf_nan=False)
    rate_limit_delay: float = Field(default=0.5, ge=0, allow_inf_nan=False)
    default_search_size: int = Field(default=10, ge=0, le=10000)
    default_sort_order: Literal["asc", "desc"] = "desc"
    default_download_formats: tuple[Literal["json", "html", "pdf"], ...] = ("json", "html", "pdf")
    default_date_output_format: str = "%d.%m.%Y"

    @field_validator("base_url", "docs_url", "search_url")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        """Accept HTTP endpoints without embedded credentials, queries or fragments."""
        url = TypeAdapter(HttpUrl).validate_python(value)
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("Endpoints cannot contain credentials, queries or fragments")
        return str(url)

    @field_validator("default_download_formats", mode="before")
    @classmethod
    def normalize_formats(cls, value: object) -> object:
        """Accept YAML sequences while retaining immutable defaults."""
        return tuple(value) if isinstance(value, list) else value


DEFAULT_CONFIG = EntscheidsucheConfig()


def load_config(config_path: Path | str | None = None) -> EntscheidsucheConfig:
    """Load settings, using defaults only when the implicit config file is absent.

    Raises:
        FileNotFoundError: An explicitly selected configuration file is missing.
        ValueError: The configuration is invalid.
        TypeError: The YAML root or client section is not a mapping.
    """
    path = Path(config_path) if config_path is not None else Path("config.yaml")
    try:
        with path.open(encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)
    except FileNotFoundError:
        if config_path is not None:
            raise
        return DEFAULT_CONFIG

    if raw_config is None:
        raw_config = {}
    if not isinstance(raw_config, dict):
        raise TypeError("Config file must contain a mapping")
    section = raw_config.get("entscheidsuche", raw_config)
    if not isinstance(section, dict):
        raise TypeError("The 'entscheidsuche' config section must be a mapping")
    return EntscheidsucheConfig.model_validate(section)
