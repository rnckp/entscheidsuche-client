"""
Independent entscheidsuche.ch API client

A Python package to access entscheidsuche.ch endpoints for Swiss court decisions.
This package is not official, endorsed by, associated with, or affiliated with entscheidsuche.ch.
"""

from .client import EntscheidsucheClient
from .models import (
    CaseDocument,
    IndexFile,
    JobsFile,
    ScraperInfo,
    SearchResult,
)

__version__ = "0.1.0"
__all__ = [
    "CaseDocument",
    "EntscheidsucheClient",
    "IndexFile",
    "JobsFile",
    "ScraperInfo",
    "SearchResult",
]
