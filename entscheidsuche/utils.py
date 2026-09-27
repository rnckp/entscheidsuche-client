"""
Utility functions for working with entscheidsuche.ch data.
"""

import re
from datetime import date
from pathlib import Path
from typing import Any

from .config import load_config
from .models import CaseDocument, SearchResult


def parse_case_number(case_number: str) -> dict[str, str | None]:
    """
    Parse a Swiss case number into its components.

    Recognized patterns:
    - "4A_123/2023" (Federal Court)
    - "A-1234/2023" (Federal Administrative Court)

    Other forms, such as "VB.2023.00123", only yield the first four-digit year.

    Args:
        case_number: The case number string.

    Returns:
        Dict with court, chamber, number, year, and original input. Unrecognized
        components are None.
    """
    result: dict[str, str | None] = {
        "court": None,
        "chamber": None,
        "number": None,
        "year": None,
        "original": case_number,
    }

    # Federal Court pattern: 4A_123/2023
    federal_pattern = r"^(\d[A-Z])_(\d+)/(\d{4})$"
    match = re.match(federal_pattern, case_number)
    if match:
        result["court"] = "BGer"
        result["chamber"] = match.group(1)
        result["number"] = match.group(2)
        result["year"] = match.group(3)
        return result

    # Federal Administrative Court pattern: A-1234/2023
    bvger_pattern = r"^([A-Z])-(\d+)/(\d{4})$"
    match = re.match(bvger_pattern, case_number)
    if match:
        result["court"] = "BVGer"
        result["chamber"] = match.group(1)
        result["number"] = match.group(2)
        result["year"] = match.group(3)
        return result

    # Generic pattern with year
    year_pattern = r"(\d{4})"
    match = re.search(year_pattern, case_number)
    if match:
        result["year"] = match.group(1)

    return result


def extract_text_from_html(html: str) -> str:
    """
    Extract plain text from HTML content.

    Args:
        html: HTML string.

    Returns:
        Plain text with HTML tags removed.
    """
    # Remove script and style elements
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html)

    # Decode common HTML entities
    entities = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
        "&auml;": "ä",
        "&ouml;": "ö",
        "&uuml;": "ü",
        "&Auml;": "Ä",
        "&Ouml;": "Ö",
        "&Uuml;": "Ü",
        "&szlig;": "ß",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def format_date(date_str: str, output_format: str | None = None) -> str:
    """
    Format a date string from API format to desired format.

    Args:
        date_str: Date string in YYYY-MM-DD format.
        output_format: Desired output format (strftime format).

    Returns:
        Formatted date string.
    """
    try:
        dt = date.fromisoformat(date_str)
    except ValueError:
        return date_str
    return dt.strftime(output_format or load_config().default_date_output_format)


def filter_by_date_range(
    documents: list[CaseDocument],
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[CaseDocument]:
    """
    Filter documents by date range.

    Args:
        documents: List of CaseDocument objects.
        start_date: Minimum date (YYYY-MM-DD).
        end_date: Maximum date (YYYY-MM-DD).

    Returns:
        Filtered list of documents.
    """
    result = []
    for doc in documents:
        if start_date and doc.date < start_date:
            continue
        if end_date and doc.date > end_date:
            continue
        result.append(doc)
    return result


def filter_by_language(
    documents: list[CaseDocument],
    language: str,
) -> list[CaseDocument]:
    """
    Filter documents by language.

    Args:
        documents: List of CaseDocument objects.
        language: Language code ("de", "fr", "it").

    Returns:
        Filtered list of documents.
    """
    return [doc for doc in documents if doc.language == language]


def group_by_spider(documents: list[CaseDocument]) -> dict[str, list[CaseDocument]]:
    """
    Group documents by their spider/scraper.

    Args:
        documents: List of CaseDocument objects.

    Returns:
        Dict mapping spider name to list of documents.
    """
    result: dict[str, list[CaseDocument]] = {}
    for doc in documents:
        if doc.spider not in result:
            result[doc.spider] = []
        result[doc.spider].append(doc)
    return result


def group_by_canton(documents: list[CaseDocument]) -> dict[str, list[CaseDocument]]:
    """
    Group documents by canton.

    Args:
        documents: List of CaseDocument objects.

    Returns:
        Dict mapping canton code to list of documents.
    """
    result: dict[str, list[CaseDocument]] = {}
    for doc in documents:
        canton = doc.spider.split("_")[0] if "_" in doc.spider else "XX"
        if canton not in result:
            result[canton] = []
        result[canton].append(doc)
    return result


def group_by_year(documents: list[CaseDocument]) -> dict[str, list[CaseDocument]]:
    """
    Group documents by year.

    Args:
        documents: List of CaseDocument objects.

    Returns:
        Dict mapping year to list of documents.
    """
    result: dict[str, list[CaseDocument]] = {}
    for doc in documents:
        year = doc.date[:4] if doc.date else "unknown"
        if year not in result:
            result[year] = []
        result[year].append(doc)
    return result


def search_results_to_dataframe(results: SearchResult) -> Any:
    """
    Convert search results to a pandas DataFrame.

    Args:
        results: SearchResult from a search query.

    Returns:
        pandas DataFrame with search results.

    Raises:
        ImportError: If pandas is not installed.
    """
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError(
            "pandas is required for this function. Install with: uv add pandas"
        ) from e

    rows = []
    for hit in results.hits:
        title = hit.title
        abstract = hit.abstract
        rows.append(
            {
                "signatur": hit.signatur,
                "spider": hit.spider,
                "date": hit.date,
                "language": hit.language,
                "score": hit.score,
                "title_de": title.get("de", "") if isinstance(title, dict) else str(title),
                "abstract_de": abstract.get("de", "")
                if isinstance(abstract, dict)
                else str(abstract),
                "content_url": hit.content_url,
                "references": ", ".join(hit.reference) if hit.reference else "",
            }
        )

    return pd.DataFrame(rows)


def documents_to_dataframe(documents: list[CaseDocument]) -> Any:
    """
    Convert a list of CaseDocuments to a pandas DataFrame.

    Args:
        documents: List of CaseDocument objects.

    Returns:
        pandas DataFrame with document data.

    Raises:
        ImportError: If pandas is not installed.
    """
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError(
            "pandas is required for this function. Install with: uv add pandas"
        ) from e

    rows = []
    for doc in documents:
        rows.append(
            {
                "signatur": doc.signatur,
                "spider": doc.spider,
                "date": doc.date,
                "language": doc.language,
                "url": doc.url,
                "html_url": doc.html_url,
                "pdf_url": doc.pdf_url,
                "case_numbers": ", ".join(doc.num),
                "kopfzeile_de": doc.kopfzeile.get("de", ""),
                "abstract_de": doc.abstract.get("de", ""),
            }
        )

    return pd.DataFrame(rows)


def build_search_query(
    text: str | None = None,
    case_number: str | None = None,
    canton: str | None = None,
    court: str | None = None,
    year: int | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Build an Elasticsearch query dict from search parameters.

    Args:
        text: Full-text search query.
        case_number: Specific case number to search for.
        canton: Canton code filter.
        court: Court name filter.
        year: Year filter.
        language: Language filter.

    Returns:
        Elasticsearch query body dict.
    """
    must: list[dict[str, Any]] = []
    filter_: list[dict[str, Any]] = []

    if text:
        must.append(
            {
                "query_string": {
                    "query": text,
                    "default_operator": "AND",
                }
            }
        )

    if case_number:
        must.append({"match": {"reference": case_number}})

    if canton:
        filter_.append({"term": {"hierarchy": canton.upper()}})

    if court:
        filter_.append({"term": {"hierarchy": court}})

    if year:
        filter_.append(
            {
                "range": {
                    "date": {
                        "gte": f"{year}-01-01",
                        "lte": f"{year}-12-31",
                    }
                }
            }
        )

    if language:
        filter_.append({"term": {"attachment.language": language}})

    query: dict[str, Any] = {
        "query": {
            "bool": {
                "must": must if must else [{"match_all": {}}],
                "filter": filter_,
            }
        }
    }

    return query


def save_document_batch(
    documents: list[CaseDocument],
    output_file: Path,
    format_: str = "json",
) -> None:
    """
    Save a batch of documents to a file.

    Args:
        documents: List of CaseDocument objects.
        output_file: Path to output file.
        format_: Output format ("json" or "csv").
    """
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if format_ == "json":
        import json

        data = [
            {
                "signatur": doc.signatur,
                "spider": doc.spider,
                "date": doc.date,
                "language": doc.language,
                "url": doc.url,
                "html_url": doc.html_url,
                "pdf_url": doc.pdf_url,
                "case_numbers": doc.num,
                "kopfzeile": doc.kopfzeile,
                "abstract": doc.abstract,
            }
            for doc in documents
        ]
        output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    elif format_ == "csv":
        df = documents_to_dataframe(documents)
        df.to_csv(output_file, index=False, encoding="utf-8")
    else:
        raise ValueError(f"Unsupported format: {format_}")


def get_statistics(documents: list[CaseDocument]) -> dict[str, Any]:
    """
    Calculate statistics for a list of documents.

    Args:
        documents: List of CaseDocument objects.

    Returns:
        Dict with various statistics.
    """
    by_canton = group_by_canton(documents)
    by_year = group_by_year(documents)
    by_language = {}
    for doc in documents:
        lang = doc.language
        by_language[lang] = by_language.get(lang, 0) + 1

    known_years = sorted(year for year in by_year if re.fullmatch(r"\d{4}", year))

    return {
        "total": len(documents),
        "by_canton": {k: len(v) for k, v in by_canton.items()},
        "by_year": {k: len(v) for k, v in sorted(by_year.items())},
        "by_language": by_language,
        "cantons_count": len(by_canton),
        "years_span": (known_years[0], known_years[-1]) if known_years else None,
    }
