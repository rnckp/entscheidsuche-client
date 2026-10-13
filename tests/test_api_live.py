"""Small, rate-limited compatibility checks for the current public API."""

import pytest

from entscheidsuche import EntscheidsucheClient

pytestmark = pytest.mark.live_api


def test_current_search_jobs_and_facets_contracts() -> None:
    with EntscheidsucheClient() as client:
        result = client.search("", spider="CH_BPatG", size=1)
        assert result.is_complete
        assert result.total_relation in {"eq", "gte"}
        assert result.hits
        hit = result.hits[0]
        assert hit.spider == "CH_BPatG"
        assert hit.court_id == "CH_PATG"
        document = client.get_document_json(hit.spider, hit.signatur)
        assert document.document_id == hit.signatur
        assert document.spider == hit.spider
        assert document.pdf_url or document.html_url
        jobs = client.get_jobs("CH_BPatG")
        assert jobs.job
        assert jobs.files
        assert hit.signatur in jobs.documents
        index = client.get_index("CH_BPatG")
        assert index.job
        assert index.total_count > 0
        facets = client.get_facets()
        assert facets["CH"].gerichte["CH_PATG"].kammern["CH_PATG_001"].spider == "CH_BPatG"
