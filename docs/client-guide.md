# Entscheidsuche client guide

Detailed Python examples and client behavior. Start with the [README](../README.md) for installation
and a runnable example; see the [API compatibility notes](../API-DOCUMENTATION.md) for request
contracts and verification limits.

The examples below assume an open `client` inside a context manager, as in the README quick start.
API calls make live requests. Replace placeholder IDs and tokens with values from responses;
illustrative references may not resolve.

## Search

```python
results = client.search(
    query="Arbeitsvertrag",
    size=20,  # client accepts 0–10000
    from_=0,  # pagination offset
    canton="ZH",  # filter by canton
    spider="ZH_Obergericht",  # filter by scraper index
    hierarchy="ZH_OG",  # optional court ID from get_facets()
    language="de",  # passed through to the service
    date_from="2023-01-01",
    date_to="2023-12-31",
    sort_by="date",
    sort_order="desc",
)

# Raw Elasticsearch query
raw = client.search_raw({"query": {"match_all": {}}, "size": 5})
```

Each call returns one page; pagination is manual. `results.total_relation` is `eq` for an exact
count, `gte` for a lower bound, or `None` if not reported. `results.timed_out`, `results.shards`,
and each hit's `sort` values are retained. Timeouts or shard failures raise `IncompleteSearchError`;
its `result` attribute contains partial results. `search_raw()` preserves responses without
translating these errors. Server query limits are not established by size validation.

`spider` selects a scraper index; `hierarchy` selects a canton, court, or chamber. These IDs differ:
`CH_BPatG` is a scraper, while `CH_PATG` is a court. `hit.spider` identifies the scraper and
`hit.court_id` the court. Use `client.get_facets()` for current labels and hierarchy-to-scraper
mappings.

## Document access

```python
doc = client.get_document_json(spider, signatur)  # CaseDocument
html = client.get_document_html(spider, signatur)  # str
pdf = client.get_document_pdf(spider, signatur)  # bytes

# Download to disk
saved = client.download_document(spider, signatur, output_dir, formats=["json", "pdf"])
```

The `signatur` argument should be the full document id from a search hit, for example
`hit.signatur`. The metadata payload may contain a shorter series-level `doc.signatur`; use
`doc.document_id` for the full metadata/document id.

HTML/PDF retrieval first fetches metadata to resolve the content path. `download_document()` uses
the configured formats (JSON, HTML, PDF by default), skips HTTP 404 responses, and returns only
saved paths. It creates the output directory and overwrites matching filenames. Other errors
propagate, and files already saved are not rolled back. Direct document getters propagate 404s too.

## Index and Jobs

```python
index = client.get_index("CH_BGE")  # IndexFile - document changes
jobs = client.get_jobs("CH_BGE")  # JobsFile - per-file statuses
new_ids = jobs.get_documents_by_status("neu")  # one ID per matching document
facets = client.get_facets()  # live canton/court/chamber labels and scraper mappings
blocked = client.get_blocklist()  # list[str] - blocked documents
files = client.list_documents("CH_BGE")  # directory hrefs ending in json/html/pdf
sitemaps = client.get_sitemap_index()  # sitemap URLs; does not fetch their contents
```

The blocklist is not automatically applied to searches or downloads. Index change lists contain full
document IDs; Jobs groups per-file statuses by document ID and format. Compare job IDs and
timestamps before using these responses for synchronization: `/last` does not guarantee a current or
complete checkpoint. See the [API notes](../API-DOCUMENTATION.md#index-and-jobs-parsing) for field
mappings.

## Utilities

```python
from entscheidsuche.utils import (
    parse_case_number,  # Parse "4A_123/2023" -> components
    filter_by_date_range,  # Filter documents by date
    filter_by_language,  # Filter by language
    group_by_canton,  # Group by canton code
    group_by_year,  # Group by year
    group_by_spider,  # Group by spider
    get_statistics,  # Stats summary
    search_results_to_dataframe,  # SearchResult -> DataFrame
    documents_to_dataframe,  # list[CaseDocument] -> DataFrame
    build_search_query,  # Build ES query dict
    save_document_batch,  # Save docs to JSON/CSV
)

# Parse case numbers
parsed = parse_case_number("4A_123/2023")
# {'court': 'BGer', 'chamber': '4A', 'number': '123', 'year': '2023',
#  'original': '4A_123/2023'}
```

These helpers operate on supplied data without fetching more results. `parse_case_number()`
recognizes the federal forms `4A_123/2023` and `A-1234/2023`; otherwise it only searches for a
four-digit year. Date filtering compares strings and assumes ISO dates. Canton grouping uses the
spider prefix (or `XX` when there is no underscore), so statistics may include federal and other
source codes.

DataFrame conversion and CSV export require pandas, included in the development environment but not
the package's runtime dependencies. Batch export writes a selected metadata summary, not the
original API JSON. `extract_text_from_html()` strips tags and decodes a fixed set of entities;
`format_date()` uses `default_date_output_format` from the working-directory config unless
explicitly overridden, and returns invalid date strings unchanged.

## Static lookups

```python
EntscheidsucheClient.list_scrapers()  # list[str]
EntscheidsucheClient.list_cantons()  # dict[str, str]
EntscheidsucheClient.get_canton_name("ZH")  # "Zürich"
```

These methods return static package data, not a live inventory or coverage check. The canton mapping
includes all 26 cantons and `CH`; the scraper list is maintained in `models.py` and does not
guarantee service coverage. Prefer `get_facets()` for live mappings.
`ScraperInfo.from_status_line()` is a placeholder and does not parse status data.

## Configuration

The client loads `config.yaml` from the current working directory, falling back to built-in defaults
if that implicit file is absent. Pass `config_path` to select another file. YAML settings may be
under `entscheidsuche:` (as in the checked-in [config](../config.yaml)) or directly at the root.
Missing settings use built-in defaults; unknown settings in the selected client mapping are
rejected. When `entscheidsuche:` is present, other root sections are ignored. Constructor `timeout`
and `rate_limit_delay` arguments override the loaded values.

The synchronous HTTPX client defaults to a 30-second timeout and a 0.5-second minimum interval
between sequential request starts per instance. There is no shared rate limiter or client retry
loop. Use a context manager or call `close()`. `base_url`, `docs_url`, and `search_url` are
independent settings; changing one does not derive the others.

Configuration is validated with Pydantic: timeouts must be positive, delays must be nonnegative, and
endpoints must be HTTP(S) URLs without credentials, queries or fragments. An explicitly supplied
`config_path` must exist. Invalid metadata paths used for content retrieval and malformed blocklists
raise validation errors.

`cache_dir` is deprecated and has no effect. Passing a non-`None` value emits `DeprecationWarning`;
remove it from constructor calls. Returned documents and search hits carry the client's `docs_url`,
including during conversion and URL generation. Content paths are validated and quoted consistently
in model URLs and client getters.
