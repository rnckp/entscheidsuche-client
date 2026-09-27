from pathlib import Path

import pytest

from entscheidsuche.models import CaseDocument
from entscheidsuche.utils import (
    build_search_query,
    format_date,
    get_statistics,
    save_document_batch,
)


def test_format_date_does_not_hide_invalid_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("unknown_key: 1", encoding="utf-8")
    with pytest.raises(ValueError, match="Extra inputs"):
        format_date("2024-01-02")


def test_build_search_query_uses_live_search_fields() -> None:
    query = build_search_query(
        text="Mietvertrag",
        case_number="4A_123/2023",
        canton="zh",
        court="ZH_Obergericht",
        year=2023,
        language="de",
    )

    bool_query = query["query"]["bool"]
    assert {"match": {"reference": "4A_123/2023"}} in bool_query["must"]
    assert {"term": {"hierarchy": "ZH"}} in bool_query["filter"]
    assert {"term": {"hierarchy": "ZH_Obergericht"}} in bool_query["filter"]
    assert {"term": {"attachment.language": "de"}} in bool_query["filter"]
    assert {"range": {"date": {"gte": "2023-01-01", "lte": "2023-12-31"}}} in bool_query["filter"]


def test_save_document_batch_rejects_unknown_format(tmp_path) -> None:
    with pytest.raises(ValueError, match="Unsupported format"):
        save_document_batch([], tmp_path / "documents.txt", format_="txt")


def test_statistics_year_span_ignores_unknown_dates() -> None:
    documents = [
        CaseDocument(signatur="a", spider="CH_BGE", language="de", date=""),
        CaseDocument(signatur="b", spider="CH_BGE", language="de", date="2024-01-02"),
        CaseDocument(signatur="c", spider="ZH_OG", language="fr", date="2022-01-02"),
    ]

    stats = get_statistics(documents)

    assert stats["by_year"]["unknown"] == 1
    assert stats["years_span"] == ("2022", "2024")
