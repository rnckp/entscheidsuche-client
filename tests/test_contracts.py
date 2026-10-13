"""Regression tests for current endpoint contracts."""

import json
from pathlib import Path

import httpx
import pytest

from entscheidsuche import EntscheidsucheClient
from entscheidsuche.models import CaseDocument, IndexFile, JobsFile, SearchHit, SearchResult

FIXTURES = Path(__file__).parent / "fixtures"


def test_index_reads_actions_and_preserves_checkpoint() -> None:
    index = IndexFile.from_json(json.loads((FIXTURES / "index.json").read_text()), "CH_BGer")
    assert index.new_documents == ["doc-new"]
    assert index.updated_documents == ["doc-updated"]
    assert index.deleted_documents == ["doc-deleted"]
    assert index.total_count == 10
    assert index.job == "446973/45/2707"
    assert index.actions["CH_BGer/doc-new.json"] == "new"


def test_jobs_reads_files_and_aggregates_status_without_duplicates() -> None:
    jobs = JobsFile.from_json(json.loads((FIXTURES / "jobs.json").read_text()), "CH_BPatG")
    assert jobs.get_documents_by_status("neu") == ["doc-a"]
    assert jobs.get_documents_by_status("identisch") == ["doc-b"]
    assert jobs.get_documents_by_status("update") == ["doc-b"]
    assert jobs.get_documents_by_status("nicht_mehr_da") == ["doc-c"]
    assert jobs.files["CH_BPatG/doc-b.json"].last_change == "446973/64/2135"
    assert set(jobs.documents["doc-a"]) == {"json", "pdf"}
    assert jobs.job == "446973/64/2326"
    assert jobs.lastjob["id"] == "446973/64/2325"


@pytest.mark.parametrize(
    "payload", [{"actions": {"../x.json": "new"}}, {"actions": {"S/x.json": 1}}]
)
def test_index_rejects_invalid_actions(payload: dict) -> None:
    with pytest.raises(ValueError):
        IndexFile.from_json(payload, "S")


@pytest.mark.parametrize(
    "files", [{"../x.pdf": {"status": "neu"}}, {"S/x.pdf": {}}, {"S/x.pdf": "neu"}]
)
def test_jobs_rejects_invalid_files(files: dict) -> None:
    with pytest.raises(ValueError):
        JobsFile.from_json({"dateien": files}, "S")


def test_search_retains_lower_bound_and_cursor() -> None:
    result = SearchResult.from_json(
        {
            "hits": {
                "total": {"value": 10000, "relation": "gte"},
                "hits": [{"_id": "x", "sort": [123, "x"]}],
            }
        }
    )
    assert result.total_relation == "gte"
    assert result.hits[0].sort == [123, "x"]


@pytest.mark.parametrize(
    "extra", [{"timed_out": True}, {"_shards": {"failed": 1, "failures": [{"reason": "example"}]}}]
)
def test_incomplete_search_raises_with_result(extra: dict) -> None:
    from entscheidsuche.models import IncompleteSearchError

    with pytest.raises(IncompleteSearchError) as error:
        SearchResult.from_json({"hits": {"total": 0, "hits": []}, **extra})
    assert not error.value.result.is_complete


@pytest.mark.parametrize("hierarchy", ["CH", [None], [123]])
def test_search_rejects_invalid_hierarchy(hierarchy: object) -> None:
    with pytest.raises(ValueError):
        SearchHit(id="x", score=None, source={"hierarchy": hierarchy})


def test_null_hierarchy_is_safe_and_court_is_distinct_from_spider() -> None:
    hit = SearchHit(id="x", score=None, source={"hierarchy": None})
    assert hit.court_id is None
    assert hit.spider == ""
    hit = SearchHit(
        id="x",
        score=None,
        source={
            "hierarchy": ["CH", "CH_PATG"],
            "attachment": {"content_url": "https://entscheidsuche.ch/docs/CH_BPatG/x.pdf"},
        },
    )
    assert hit.court_id == "CH_PATG"
    assert hit.spider == "CH_BPatG"


def test_search_separates_scraper_and_hierarchy_filters() -> None:
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"hits": {"total": 0, "hits": []}})

    with EntscheidsucheClient(rate_limit_delay=0, transport=httpx.MockTransport(handler)) as client:
        client.search("", spider="ZH_Obergericht", hierarchy="ZH_OG")
    filters = bodies[0]["query"]["bool"]["filter"]
    assert {"term": {"_index": "entscheidsuche.v2-zh_obergericht"}} in filters
    assert {"term": {"hierarchy": "ZH_OG"}} in filters


def test_custom_endpoint_propagates_to_documents_and_hits(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("docs_url: https://mirror.example/cases\n")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "hits": {
                        "total": 1,
                        "hits": [
                            {
                                "_id": "x",
                                "_source": {
                                    "attachment": {
                                        "content_url": "https://mirror.example/cases/Actual_Spider/x.pdf"
                                    }
                                },
                            }
                        ],
                    }
                },
            )
        return httpx.Response(200, json={"PDF": {"Datei": "Actual_Spider/x.pdf"}})

    with EntscheidsucheClient(
        config_path=config, rate_limit_delay=0, transport=httpx.MockTransport(handler)
    ) as client:
        doc = client.get_document_json("S", "x")
        converted = client.search("").hits[0].to_case_document()
    assert doc.json_url == "https://mirror.example/cases/x.json"
    assert doc.pdf_url == converted.pdf_url == "https://mirror.example/cases/Actual_Spider/x.pdf"
    assert converted.spider == "Actual_Spider"


@pytest.mark.parametrize(
    "path", ["../escape.pdf", "%2e%2e/escape.pdf", "https://other.example/x.pdf"]
)
def test_model_urls_use_same_path_validation_as_getters(path: str) -> None:
    doc = CaseDocument("x", "S", "de", "", pdf_path=path)
    with pytest.raises(ValueError):
        _ = doc.pdf_url


def test_cache_dir_warns_and_does_not_create_directory(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    with pytest.warns(DeprecationWarning, match="cache_dir"), EntscheidsucheClient(cache_dir=cache):
        pass
    assert not cache.exists()


def test_representative_search_fixture_validates_source_and_shards() -> None:
    result = SearchResult.from_json(json.loads((FIXTURES / "search.json").read_text()))
    hit = result.hits[0]
    assert result.total == 10000
    assert result.total_relation == "gte"
    assert result.shards.successful == 53
    assert hit.spider == "AG_Baugesetzgebung"
    assert hit.court_id == "AG_BG"
    assert hit.title["fr"] == "Exemple"
    assert hit.sort == [1427673600000, "example-id"]


def test_get_facets_exposes_live_hierarchy_and_scraper_mapping() -> None:
    payload = json.loads((FIXTURES / "facets.json").read_text())
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, json=payload)

    with EntscheidsucheClient(rate_limit_delay=0, transport=httpx.MockTransport(handler)) as client:
        facets = client.get_facets()
    assert requests == ["https://entscheidsuche.ch/docs/Facetten.json"]
    assert facets["CH"].gerichte["CH_PATG"].kammern["CH_PATG_001"].spider == "CH_BPatG"


@pytest.mark.parametrize(
    "source",
    [
        {"title": "bad"},
        {"abstract": [1]},
        {"attachment": {"language": 2}},
        {"attachment": {"content_url": []}},
        {"id": []},
    ],
)
def test_malformed_source_fails_at_parsing_boundary(source: dict) -> None:
    with pytest.raises(ValueError):
        SearchResult.from_json({"hits": {"hits": [{"_source": source}]}})


def test_index_prefers_overall_total_to_partial_signature_counts() -> None:
    index = IndexFile.from_json(
        {"actions": {}, "gesamt": {"gesamt": 10}, "signaturen": {"S_001": {"gesamt": 2}}}, "S"
    )
    assert index.total_count == 10


def test_index_falls_back_to_signature_counts_without_overall_total() -> None:
    index = IndexFile.from_json(
        {"actions": {}, "signaturen": {"S_001": {"gesamt": 2}, "S_002": {"gesamt": 3}}}, "S"
    )
    assert index.total_count == 5


@pytest.mark.parametrize(
    "parser,payload", [(IndexFile, {"signaturen": {}}), (JobsFile, {"signaturen": {}})]
)
def test_obsolete_summary_only_contracts_are_rejected(parser: type, payload: dict) -> None:
    with pytest.raises(ValueError):
        parser.from_json(payload, "S")


def test_known_index_fallback_preserves_scraper_casing() -> None:
    hit = SearchHit(id="x", score=None, source={}, index="entscheidsuche.v2-ch_bpatg")
    assert hit.spider == "CH_BPatG"
    assert hit.court_id is None


def test_successful_null_source_fields_have_safe_defaults() -> None:
    hit = SearchHit(
        id="x",
        score=None,
        source={"title": None, "abstract": None, "meta": None, "attachment": None, "Sprache": None},
    )
    assert hit.title == hit.abstract == {}
    assert hit.to_case_document().language == "de"


def test_incomplete_response_preserves_partial_hits_and_failure_details() -> None:
    from entscheidsuche import IncompleteSearchError

    with pytest.raises(IncompleteSearchError) as error:
        SearchResult.from_json(
            {
                "timed_out": True,
                "_shards": {"failed": 1, "failures": [{"reason": "test failure"}]},
                "hits": {"total": {"value": 1, "relation": "eq"}, "hits": [{"_id": "partial"}]},
            }
        )
    assert error.value.result.hits[0].signatur == "partial"
    assert error.value.result.shards.failures == [{"reason": "test failure"}]


def test_raw_search_preserves_incomplete_response_without_translation() -> None:
    payload = {"timed_out": True, "_shards": {"failed": 1}, "hits": {"total": 0, "hits": []}}
    with EntscheidsucheClient(
        rate_limit_delay=0,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    ) as client:
        assert client.search_raw({"size": 0}) == payload


def test_custom_html_urls_quote_paths_consistently_with_getter(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("docs_url: https://mirror.example/cases/\n")
    urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if request.url.path.endswith(".json"):
            return httpx.Response(200, json={"HTML": {"Datei": "Actual_Spider/a b.html"}})
        return httpx.Response(200, text="<p>example</p>")

    with EntscheidsucheClient(
        config_path=config, rate_limit_delay=0, transport=httpx.MockTransport(handler)
    ) as client:
        doc = client.get_document_json("S", "a b")
        assert client.get_document_html("S", "a b") == "<p>example</p>"
    assert doc.html_url == urls[-1] == "https://mirror.example/cases/Actual_Spider/a%20b.html"
    assert doc.json_url == urls[0] == "https://mirror.example/cases/a%20b.json"
