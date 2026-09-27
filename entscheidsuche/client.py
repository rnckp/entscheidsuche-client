"""
Main client for the entscheidsuche.ch API.
"""

import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Self
from urllib.parse import quote, unquote
from xml.etree import ElementTree

import httpx
from pydantic import ConfigDict, TypeAdapter

from .config import EntscheidsucheConfig, load_config
from .models import (
    CANTONS,
    SCRAPERS,
    CaseDocument,
    IndexFile,
    JobsFile,
    SearchResult,
)

ALLOWED_DOCUMENT_FORMATS = {"json", "html", "pdf"}
_BLOCKLIST = TypeAdapter(
    list[str] | dict[str, list[str]],
    config=ConfigDict(strict=True, hide_input_in_errors=True),
)


class _DirectoryListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if href and href.endswith((".json", ".html", ".pdf")):
            self.links.append(href)


def _validate_identifier(value: str, name: str) -> str:
    if not value or "/" in value or "\\" in value or value in {".", ".."}:
        raise ValueError(f"Invalid {name}: {value!r}")
    return value


def _quote_segment(value: str) -> str:
    return quote(value, safe="")


def _validate_document_path(value: str) -> str:
    """Constrain remote metadata to a relative path below the docs endpoint."""
    decoded = unquote(value)
    if (
        any(character in decoded for character in "\\?#:%")
        or any(ord(character) < 32 or ord(character) == 127 for character in decoded)
        or any(part in {"", ".", ".."} for part in decoded.split("/"))
    ):
        raise ValueError("Invalid document path in metadata")
    return "/".join(_quote_segment(part) for part in decoded.split("/"))


class EntscheidsucheClient:
    """
    Client for accessing the entscheidsuche.ch API.

    This client provides methods to:
    - Search for court decisions using Elasticsearch
    - List and download documents (JSON, PDF, HTML)
    - Access index and jobs files for scrapers
    - Get the blocklist of removed documents

    Example:
        >>> client = EntscheidsucheClient()
        >>> results = client.search("Mietvertrag")
        >>> for hit in results.hits:
        ...     print(hit.signatur, hit.date)
    """

    def __init__(
        self,
        timeout: float | None = None,
        rate_limit_delay: float | None = None,
        cache_dir: Path | None = None,
        config_path: Path | str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """
        Initialize the client.

        Args:
            timeout: Request timeout in seconds.
            rate_limit_delay: Minimum delay between requests in seconds.
            cache_dir: Reserved for future caching; currently has no effect.
            config_path: Optional path to a config.yaml file.
            transport: Optional HTTPX transport, mainly useful for tests.
        """
        settings = load_config(config_path).model_dump()
        if timeout is not None:
            settings["timeout"] = timeout
        if rate_limit_delay is not None:
            settings["rate_limit_delay"] = rate_limit_delay
        self.config = EntscheidsucheConfig.model_validate(settings)
        self.base_url = self.config.base_url.rstrip("/")
        self.docs_url = self.config.docs_url.rstrip("/")
        self.search_url = self.config.search_url
        self.timeout = self.config.timeout
        self.rate_limit_delay = self.config.rate_limit_delay
        self.cache_dir = cache_dir
        self._last_request_time = 0.0
        self._client = httpx.Client(timeout=self.timeout, transport=transport)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.monotonic()

    def _get(self, url: str) -> httpx.Response:
        """Make a rate-limited GET request."""
        self._rate_limit()
        response = self._client.get(url)
        response.raise_for_status()
        return response

    def _post(self, url: str, json_data: dict[str, Any]) -> httpx.Response:
        """Make a rate-limited POST request."""
        self._rate_limit()
        response = self._client.post(url, json=json_data)
        response.raise_for_status()
        return response

    # -------------------------------------------------------------------------
    # Search API
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        size: int | None = None,
        from_: int = 0,
        canton: str | None = None,
        spider: str | None = None,
        language: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> SearchResult:
        """
        Search for court decisions using Elasticsearch.

        Args:
            query: Search query string.
            size: Number of results to return (default 10, max 10000).
            from_: Offset for pagination.
            canton: Filter by canton code (e.g., "ZH", "BE").
            spider: Filter by spider/scraper name.
            language: Filter by language ("de", "fr", "it").
            date_from: Filter by minimum date (YYYY-MM-DD).
            date_to: Filter by maximum date (YYYY-MM-DD).
            sort_by: Field to sort by (e.g., "date", "_score").
            sort_order: Sort order ("asc" or "desc").

        Returns:
            SearchResult containing hits and metadata.
        """
        result_size = size if size is not None else self.config.default_search_size
        order = sort_order if sort_order is not None else self.config.default_sort_order
        if type(result_size) is not int or not 0 <= result_size <= 10000:
            raise ValueError("size must be an integer between 0 and 10000")
        if type(from_) is not int or from_ < 0:
            raise ValueError("from_ must be a nonnegative integer")
        if order not in {"asc", "desc"}:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        must_clauses: list[dict[str, Any]] = []
        filter_clauses: list[dict[str, Any]] = []

        if query:
            must_clauses.append(
                {
                    "query_string": {
                        "query": query,
                        "default_operator": "AND",
                    }
                }
            )

        if canton:
            filter_clauses.append({"term": {"hierarchy": canton.upper()}})

        if spider:
            filter_clauses.append({"term": {"hierarchy": spider}})

        if language:
            filter_clauses.append({"term": {"attachment.language": language}})

        if date_from or date_to:
            date_range: dict[str, str] = {}
            if date_from:
                date_range["gte"] = date_from
            if date_to:
                date_range["lte"] = date_to
            filter_clauses.append({"range": {"date": date_range}})

        query_body: dict[str, Any] = {
            "size": result_size,
            "from": from_,
        }

        if must_clauses or filter_clauses:
            query_body["query"] = {
                "bool": {
                    "must": must_clauses if must_clauses else [{"match_all": {}}],
                    "filter": filter_clauses,
                }
            }

        if sort_by:
            query_body["sort"] = [{sort_by: {"order": order}}]

        response = self._post(self.search_url, query_body)
        return SearchResult.from_json(response.json())

    def search_raw(self, query_body: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a raw Elasticsearch query.

        Args:
            query_body: Complete Elasticsearch query body.

        Returns:
            Raw JSON response from Elasticsearch.
        """
        response = self._post(self.search_url, query_body)
        return response.json()

    # -------------------------------------------------------------------------
    # Document Access
    # -------------------------------------------------------------------------

    def get_document_json(self, spider: str, signatur: str) -> CaseDocument:
        """
        Get the JSON metadata for a document.

        Args:
            spider: Spider/scraper name (e.g., "CH_BGE").
            signatur: Document signature.

        Returns:
            CaseDocument with all metadata.
        """
        _validate_identifier(spider, "spider")
        _validate_identifier(signatur, "signatur")
        url = f"{self.docs_url}/{_quote_segment(signatur)}.json"
        response = self._get(url)
        return CaseDocument.from_json(response.json(), document_id=signatur)

    def _document_path(self, spider: str, signatur: str, format_: str) -> str:
        document = self.get_document_json(spider, signatur)
        if format_ == "html" and document.html_path:
            return _validate_document_path(document.html_path)
        if format_ == "pdf" and document.pdf_path:
            return _validate_document_path(document.pdf_path)
        return f"{_quote_segment(spider)}/{_quote_segment(signatur)}.{format_}"

    def get_document_html(self, spider: str, signatur: str) -> str:
        """
        Get the HTML content of a document.

        Args:
            spider: Spider/scraper name.
            signatur: Document signature.

        Returns:
            HTML content as string.
        """
        _validate_identifier(spider, "spider")
        _validate_identifier(signatur, "signatur")
        path = self._document_path(spider, signatur, "html")
        url = f"{self.docs_url}/{path}"
        response = self._get(url)
        return response.text

    def get_document_pdf(self, spider: str, signatur: str) -> bytes:
        """
        Get the PDF content of a document.

        Args:
            spider: Spider/scraper name.
            signatur: Document signature.

        Returns:
            PDF content as bytes.
        """
        _validate_identifier(spider, "spider")
        _validate_identifier(signatur, "signatur")
        path = self._document_path(spider, signatur, "pdf")
        url = f"{self.docs_url}/{path}"
        response = self._get(url)
        return response.content

    def download_document(
        self,
        spider: str,
        signatur: str,
        output_dir: Path,
        formats: list[str] | None = None,
    ) -> dict[str, Path]:
        """
        Download document files to a local directory.

        Args:
            spider: Spider/scraper name.
            signatur: Document signature.
            output_dir: Directory to save files.
            formats: List of formats to download ("json", "html", "pdf").
                     If None, downloads all available formats.

        Returns:
            Dict mapping format to saved file path.
        """
        if formats is None:
            formats = list(self.config.default_download_formats)

        _validate_identifier(spider, "spider")
        safe_signatur = _validate_identifier(signatur, "signatur")
        unsupported_formats = sorted(set(formats) - ALLOWED_DOCUMENT_FORMATS)
        if unsupported_formats:
            raise ValueError(f"Unsupported document formats: {', '.join(unsupported_formats)}")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files: dict[str, Path] = {}

        for fmt in formats:
            try:
                if fmt == "json":
                    url = f"{self.docs_url}/{_quote_segment(signatur)}.json"
                    response = self._get(url)
                    file_path = output_dir / f"{safe_signatur}.json"
                    file_path.write_text(response.text, encoding="utf-8")
                    saved_files["json"] = file_path
                elif fmt == "html":
                    content = self.get_document_html(spider, signatur)
                    file_path = output_dir / f"{safe_signatur}.html"
                    file_path.write_text(content, encoding="utf-8")
                    saved_files["html"] = file_path
                elif fmt == "pdf":
                    content = self.get_document_pdf(spider, signatur)
                    file_path = output_dir / f"{safe_signatur}.pdf"
                    file_path.write_bytes(content)
                    saved_files["pdf"] = file_path
            except httpx.HTTPStatusError as error:
                if error.response.status_code != 404:
                    raise

        return saved_files

    # -------------------------------------------------------------------------
    # Index and Jobs Files
    # -------------------------------------------------------------------------

    def get_index(self, spider: str) -> IndexFile:
        """
        Get the latest index file for a spider.

        Args:
            spider: Spider/scraper name.

        Returns:
            IndexFile with document changes.
        """
        _validate_identifier(spider, "spider")
        url = f"{self.docs_url}/Index/{_quote_segment(spider)}/last"
        response = self._get(url)
        return IndexFile.from_json(response.json(), spider)

    def get_jobs(self, spider: str) -> JobsFile:
        """
        Get the latest jobs file for a spider.

        Args:
            spider: Spider/scraper name.

        Returns:
            JobsFile with all document statuses.
        """
        _validate_identifier(spider, "spider")
        url = f"{self.docs_url}/Jobs/{_quote_segment(spider)}/last"
        response = self._get(url)
        return JobsFile.from_json(response.json(), spider)

    # -------------------------------------------------------------------------
    # Blocklist
    # -------------------------------------------------------------------------

    def get_blocklist(self) -> list[str]:
        """
        Get the list of blocked document names.

        Returns:
            List of blocked document signatures.
        """
        url = f"{self.docs_url}/Blockliste.json"
        response = self._get(url)
        data = _BLOCKLIST.validate_python(response.json())
        if isinstance(data, list):
            return data
        if "blocked" in data:
            return data["blocked"]
        return [document_id for values in data.values() for document_id in values]

    # -------------------------------------------------------------------------
    # Directory Listing
    # -------------------------------------------------------------------------

    def list_documents(self, spider: str) -> list[str]:
        """
        List all document files for a spider.

        Note: This parses the HTML directory listing which may include
        outdated files that are no longer indexed.

        Args:
            spider: Spider/scraper name.

        Returns:
            List of filenames in the spider's directory.
        """
        _validate_identifier(spider, "spider")
        url = f"{self.docs_url}/{_quote_segment(spider)}/"
        response = self._get(url)
        parser = _DirectoryListingParser()
        parser.feed(response.text)
        return sorted(set(parser.links))

    # -------------------------------------------------------------------------
    # Sitemap
    # -------------------------------------------------------------------------

    def get_sitemap_index(self) -> list[str]:
        """
        Get the list of sitemap URLs from the sitemap index.

        Returns:
            List of sitemap URLs.
        """
        url = f"{self.base_url}/sitemapindex.xml"
        response = self._get(url)
        root = ElementTree.fromstring(response.content)
        return [
            element.text for element in root.iter() if element.tag.endswith("loc") and element.text
        ]

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def get_canton_name(code: str) -> str | None:
        """Get the full canton name from a code."""
        return CANTONS.get(code.upper())

    @staticmethod
    def get_canton_from_spider(spider: str) -> str | None:
        """Extract the canton code from a spider name."""
        if "_" in spider:
            return spider.split("_")[0]
        return None

    @staticmethod
    def list_scrapers() -> list[str]:
        """Get list of known scrapers."""
        return SCRAPERS.copy()

    @staticmethod
    def list_cantons() -> dict[str, str]:
        """Get dict of canton codes to names."""
        return CANTONS.copy()
