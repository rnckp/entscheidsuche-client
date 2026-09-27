import pytest

from entscheidsuche.models import CaseDocument, JobsFile, SearchHit, SearchResult


@pytest.mark.parametrize("payload", [[], {"Datum": []}, {"Signatur": {}}])
def test_invalid_document_metadata_is_rejected(payload: object) -> None:
    with pytest.raises(ValueError):
        CaseDocument.from_json(payload)


@pytest.mark.parametrize(
    "payload", [[], {"hits": []}, {"hits": {"hits": [None]}}, {"hits": {"hits": [{"_source": []}]}}]
)
def test_invalid_search_response_is_rejected(payload: object) -> None:
    with pytest.raises(ValueError):
        SearchResult.from_json(payload)


def test_search_result_accepts_null_scores_when_sorted() -> None:
    result = SearchResult.from_json(
        {"hits": {"total": {"value": 1}, "hits": [{"_id": "doc", "_score": None}]}}
    )
    assert result.hits[0].score is None


def test_search_hit_language_falls_back_to_metadata() -> None:
    hit = SearchHit(id="doc", score=0, source={"Sprache": "fr"})
    assert hit.language == "fr"


def test_jobs_returns_document_ids_once_for_matching_formats() -> None:
    jobs = JobsFile.from_json(
        {
            "signaturen": {
                "doc-a": {"json": "neu", "html": "neu", "pdf": {"status": "update"}},
                "doc-b": {"json": "identisch"},
            }
        },
        "CH_BGE",
    )
    assert jobs.get_documents_by_status("neu") == ["doc-a"]
    assert jobs.get_documents_by_status("update") == ["doc-a"]
    assert jobs.get_documents_by_status("identisch") == ["doc-b"]


def test_case_document_parses_live_metadata_shape() -> None:
    document = CaseDocument.from_json(
        {
            "Signatur": "CH_BGE_012",
            "Spider": "CH_BGE",
            "Sprache": "fr",
            "Datum": "2006-08-31",
            "HTML": {
                "Datei": "CH_BGE/CH_BGE_012_20060831-7143-03_2006-08-31.html",
                "URL": "https://search.bger.ch/example",
                "Checksum": "abc",
            },
            "Num": ["20060831_7143_03"],
            "Kopfzeile": [
                {"Sprachen": ["de"], "Text": "Bundesgericht"},
                {"Sprachen": ["fr", "it"], "Text": "Tribunal fédéral"},
            ],
            "Meta": [{"Sprachen": ["de"], "Text": "Meta text"}],
            "Abstract": [{"Sprachen": ["de"], "Text": "Abstract text"}],
        },
        document_id="CH_BGE_012_20060831-7143-03_2006-08-31",
    )

    assert document.signatur == "CH_BGE_012"
    assert document.document_id == "CH_BGE_012_20060831-7143-03_2006-08-31"
    assert document.html_path == "CH_BGE/CH_BGE_012_20060831-7143-03_2006-08-31.html"
    assert document.url == "https://search.bger.ch/example"
    assert document.kopfzeile["fr"] == "Tribunal fédéral"
    assert document.meta["de"] == "Meta text"
    assert document.abstract["de"] == "Abstract text"
    assert document.json_url.endswith("/CH_BGE_012_20060831-7143-03_2006-08-31.json")


def test_search_hit_to_case_document_uses_search_index_fields() -> None:
    hit = SearchHit(
        id="AG_BG_001_Adressat-einer-Besei_1994-02-21",
        score=1.0,
        index="entscheidsuche.v2-ag_baugesetzgebung",
        source={
            "date": "1994-02-21",
            "hierarchy": ["AG", "AG_BG", "AG_BG_001"],
            "title": {"de": "Aargau Entscheidsammlung"},
            "abstract": {"de": "Abstract"},
            "meta": {"de": "Meta"},
            "reference": ["Adressat einer Beseitigungsverfügung"],
            "attachment": {
                "language": "de",
                "content_url": "https://entscheidsuche.ch/docs/AG_Baugesetzgebung/AG_BG_001_Adressat-einer-Besei_1994-02-21.pdf",
            },
        },
    )

    document = hit.to_case_document()

    assert document.signatur == "AG_BG_001_Adressat-einer-Besei_1994-02-21"
    assert document.spider == "AG_BG"
    assert document.date == "1994-02-21"
    assert document.language == "de"
    assert document.pdf_path == "AG_Baugesetzgebung/AG_BG_001_Adressat-einer-Besei_1994-02-21.pdf"
    assert document.num == ["Adressat einer Beseitigungsverfügung"]
    assert document.kopfzeile == {"de": "Aargau Entscheidsammlung"}
