"""
Independent entscheidsuche.ch API client

A Python package to access entscheidsuche.ch endpoints for Swiss court decisions.
This package is not official, endorsed by, associated with, or affiliated with entscheidsuche.ch.
"""

from .client import EntscheidsucheClient
from .models import (
    CaseDocument,
    FacetNode,
    FileStatus,
    IncompleteSearchError,
    IndexFile,
    JobsFile,
    ScraperInfo,
    SearchHit,
    SearchResult,
    ShardInfo,
)

__version__ = "0.1.0"
__all__ = [
    "CaseDocument",
    "EntscheidsucheClient",
    "FacetNode",
    "FileStatus",
    "IncompleteSearchError",
    "IndexFile",
    "JobsFile",
    "ScraperInfo",
    "SearchHit",
    "SearchResult",
    "ShardInfo",
]
