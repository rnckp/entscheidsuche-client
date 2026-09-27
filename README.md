# Entscheidsuche Python Client

**Python client for accessing the [entscheidsuche.ch](https://entscheidsuche.ch) API and Swiss court decision data more easily.**

This project is not official, or associated with entscheidsuche.ch. It was developed independently as a convenience wrapper around publicly reachable entscheidsuche.ch endpoints.

## Installation

Requires Python 3.12 or newer and `uv`. From a local checkout:

```bash
git clone https://github.com/rnckp/entscheidsuche-client.git
cd entscheidsuche-client
uv sync
```

## Quick Start

Save the example in a Python file and run it with `uv run <file>.py` from the
repository root. It makes network requests and writes files under `downloads/`.

```python
from entscheidsuche import EntscheidsucheClient

with EntscheidsucheClient() as client:
    # Search for court decisions
    results = client.search("Mietvertrag", size=10)
    for hit in results.hits:
        print(f"{hit.signatur}: {hit.date} ({hit.language})")

    if results.hits:
        hit = results.hits[0]
        doc = client.get_document_json(hit.spider, hit.signatur)
        saved = client.download_document(hit.spider, hit.signatur, output_dir="./downloads")
```

## API Reference

The snippets below assume an open `client` as in the quick start. See
[API notes](API-DOCUMENTATION.md) for request paths and model mappings.

### Search

```python
results = client.search(
    query="Arbeitsvertrag",
    size=20,  # client accepts 0–10000
    from_=0,  # pagination offset
    canton="ZH",  # filter by canton
    spider="ZH_Obergericht",  # filter by spider
    language="de",  # passed through to the service
    date_from="2023-01-01",
    date_to="2023-12-31",
    sort_by="date",
    sort_order="desc",
)

# Raw Elasticsearch query
raw = client.search_raw({"query": {"match_all": {}}, "size": 5})
```

Each call returns one page; pagination is manual. `results.total` preserves the
reported count but discards the service's exact/lower-bound indicator. Use
`search_raw()` when that distinction matters. Server query limits are not
established by the client's size validation.

### Document Access

```python
doc = client.get_document_json(spider, signatur)  # CaseDocument
html = client.get_document_html(spider, signatur)  # str
pdf = client.get_document_pdf(spider, signatur)  # bytes

# Download to disk
saved = client.download_document(spider, signatur, output_dir, formats=["json", "pdf"])
```

The `signatur` argument should be the full document id from a search hit, for example `hit.signatur`. The metadata payload may contain a shorter series-level `doc.signatur`; use `doc.document_id` for the full metadata/document id.

HTML/PDF retrieval first fetches metadata to resolve the content path.
`download_document()` uses the configured formats (JSON, HTML, PDF by default),
skips HTTP 404 responses, and returns only saved paths. It creates the output
directory and overwrites matching filenames. Other errors propagate, and files
already saved are not rolled back. Direct document getters propagate 404s too.

### Configuration

The client loads `config.yaml` from the current working directory, falling back
to built-in defaults if that implicit file is absent. Pass `config_path` to select
another file. YAML settings may be under `entscheidsuche:` (as in the checked-in
[config](config.yaml)) or directly at the root. Missing settings use built-in
defaults; unknown settings are rejected. Constructor `timeout` and
`rate_limit_delay` arguments override the loaded values.

The synchronous HTTPX client defaults to a 30-second timeout and a 0.5-second
minimum interval between sequential request starts per instance. There is no
shared rate limiter or client retry loop. Use a context manager or call `close()`.
`base_url`, `docs_url`, and `search_url` are independent settings; changing one does
not derive the others.

Configuration is validated with Pydantic: timeouts must be positive, delays must be
nonnegative, and endpoints must be HTTP(S) URLs without credentials, queries or
fragments. An explicitly supplied `config_path` must exist. Invalid metadata
paths used for content retrieval and malformed blocklists raise validation errors.

`cache_dir` is reserved and does not enable caching. `CaseDocument` URL properties
and content-path extraction in `SearchHit.to_case_document()` use the built-in
docs endpoint, even when the client uses custom endpoints.

### Index & Jobs

```python
index = client.get_index("CH_BGE")  # IndexFile - document changes
jobs = client.get_jobs("CH_BGE")  # JobsFile - document statuses
blocked = client.get_blocklist()  # list[str] - blocked documents
files = client.list_documents("CH_BGE")  # directory hrefs ending in json/html/pdf
sitemaps = client.get_sitemap_index()  # sitemap URLs; does not fetch their contents
```

The blocklist is not automatically applied to searches or downloads. Index and
jobs results reflect the parser's expected shapes; see the [API notes](API-DOCUMENTATION.md)
for validation limits.

### Utilities

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

These helpers operate on supplied data without fetching more results.
`parse_case_number()` recognizes the federal forms `4A_123/2023` and `A-1234/2023`;
otherwise it only searches for a four-digit year. Date filtering compares strings
and assumes ISO dates. Canton grouping uses the spider prefix (or `XX` when absent),
so statistics may include federal and other source codes.

DataFrame conversion and CSV export require pandas, included in the development
environment but not the package's runtime dependencies. Batch export writes a
selected metadata summary, not the original API JSON. `extract_text_from_html()`
strips tags and decodes a fixed set of entities; `format_date()` uses
`default_date_output_format` from the working-directory config unless explicitly
overridden, and returns invalid date strings unchanged.

### Static Methods

```python
EntscheidsucheClient.list_scrapers()  # list[str]
EntscheidsucheClient.list_cantons()  # dict[str, str]
EntscheidsucheClient.get_canton_name("ZH")  # "Zürich"
```

These methods return static package data, not a live inventory or coverage check.
The canton mapping includes all 26 cantons and `CH`; the scraper list is not a
guarantee of complete or current service coverage. `ScraperInfo.from_status_line()`
is a placeholder and does not parse status data.

## Development and Examples

- `entscheidsuche/client.py`: synchronous HTTP requests and file downloads.
- `entscheidsuche/models.py`: Pydantic dataclasses, response parsing, static lookups.
- `entscheidsuche/config.py`: validated YAML settings and built-in defaults.
- `entscheidsuche/utils.py`: local queries, transformations, statistics, and exports.
- `tests/`: local tests with mocked HTTP responses; no live API contract suite.
- `main.py`: search demo, run with `uv run main.py` (makes network requests).
- [Example notebook](examples/entscheidsuche_demo.ipynb): launch with
  `uv run jupyter lab` after `uv sync`, using the repository environment as kernel.
- [NOTES.md](NOTES.md): implementation rationale;
  [PLAN.md](PLAN.md): unresolved findings.

Run local checks from the repository root:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Use `uv run ruff format .` to apply formatting. Dependabot is configured in
`.github/dependabot.yml`; there is no checked-in CI workflow or pre-commit setup.
Contributor policies are in [AGENTS.md](AGENTS.md).

## Fair Use

This independent client accesses entscheidsuche.ch endpoints.

> [!IMPORTANT]
> Please be kind to the server, mention entscheidsuche.ch as the data source when appropriate, and **consider supporting entscheidsuche.ch if using the data commercially.**

## License

This Python client is licensed under the MIT License.

The MIT License applies only to this client code. It does not apply to Entscheidsuche data, API content, court decisions, or other source materials returned by the service. For data and content licensing details, consult [Entscheidsuche](https://entscheidsuche.ch) and the respective original data sources.
