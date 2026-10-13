"""Explicit opt-in for read-only live API contract checks."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Require explicit authorization before network tests run."""
    parser.addoption(
        "--live-api", action="store_true", help="Run read-only entscheidsuche.ch checks"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep the default suite offline."""
    if config.getoption("--live-api"):
        return
    for item in items:
        if "live_api" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="requires explicit --live-api opt-in"))
