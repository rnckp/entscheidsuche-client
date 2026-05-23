# Entscheidsuche Python Client

**Independent Python client for accessing the [entscheidsuche.ch](https://entscheidsuche.ch) API and Swiss court decision data more easily.**

This project is not official, or associated with entscheidsuche.ch. It was developed independently as a convenience wrapper around publicly reachable entscheidsuche.ch endpoints.

## Installation

```bash
git clone https://github.com/rnckp/entscheidsuche.git
cd entscheidsuche
uv sync
```

## Quick Start

```python
from entscheidsuche import EntscheidsucheClient

with EntscheidsucheClient() as client:
    # Search for court decisions
    results = client.search("Mietvertrag", size=10)
    for hit in results.hits:
        print(f"{hit.signatur}: {hit.date} ({hit.language})")

    # Get document metadata and content
    doc = client.get_document_json("CH_BGE", "CH_BGE_001_BGE-86-I-226_1960-10-20")
    html = client.get_document_html("CH_BGE", "CH_BGE_001_BGE-86-I-226_1960-10-20")

    # Download all formats
    client.download_document("CH_BGE", "CH_BGE_001_BGE-86-I-226_1960-10-20", output_dir="./downloads")
```

## API Reference

### Search

```python
results = client.search(
    query="Arbeitsvertrag",
    size=20,                # max 10000
    from_=0,                # pagination offset
    canton="ZH",            # filter by canton
    spider="ZH_Obergericht",# filter by spider
    language="de",          # "de", "fr", "it"
    date_from="2023-01-01",
    date_to="2023-12-31",
    sort_by="date",
    sort_order="desc",
)

# Raw Elasticsearch query
raw = client.search_raw({"query": {"match_all": {}}, "size": 5})
```

### Document Access

```python
doc = client.get_document_json(spider, signatur)  # CaseDocument
html = client.get_document_html(spider, signatur) # str
pdf = client.get_document_pdf(spider, signatur)   # bytes

# Download to disk
saved = client.download_document(spider, signatur, output_dir, formats=["json", "pdf"])
```

The `signatur` argument should be the full document id from a search hit, for example `hit.signatur`. The metadata payload may contain a shorter series-level `doc.signatur`; use `doc.document_id` for the full metadata/document id.

### Configuration

Runtime defaults are loaded from `config.yaml` when present. Constructor arguments such as `timeout` and `rate_limit_delay` override the configured defaults.

### Index & Jobs

```python
index = client.get_index("CH_BGE")   # IndexFile - document changes
jobs = client.get_jobs("CH_BGE")     # JobsFile - document statuses
blocked = client.get_blocklist()     # list[str] - blocked documents
```

### Utilities

```python
from entscheidsuche.utils import (
    parse_case_number,           # Parse "4A_123/2023" -> components
    filter_by_date_range,        # Filter documents by date
    filter_by_language,          # Filter by language
    group_by_canton,             # Group by canton code
    group_by_year,               # Group by year
    group_by_spider,             # Group by spider
    get_statistics,              # Stats summary
    search_results_to_dataframe, # SearchResult -> DataFrame
    documents_to_dataframe,      # list[CaseDocument] -> DataFrame
    build_search_query,          # Build ES query dict
    save_document_batch,         # Save docs to JSON/CSV
)

# Parse case numbers
parsed = parse_case_number("4A_123/2023")
# {'court': 'BGer', 'chamber': '4A', 'number': '123', 'year': '2023'}
```

### Static Methods

```python
EntscheidsucheClient.list_scrapers()        # list[str]
EntscheidsucheClient.list_cantons()         # dict[str, str]
EntscheidsucheClient.get_canton_name("ZH")  # "Zürich"
```

## Data Sources

- **Federal**: BGE (Bundesgericht), BVGer (Bundesverwaltungsgericht), BPatG (Bundespatentgericht)
- **Cantons**: All 26 Swiss cantons (AG, AI, AR, BE, BL, BS, FR, GE, GL, GR, JU, LU, NE, NW, OW, SG, SH, SO, SZ, TG, TI, UR, VD, VS, ZG, ZH)

## Fair Use

This independent client accesses entscheidsuche.ch endpoints.

> [!IMPORTANT]
> Please be kind to the server, mention entscheidsuche.ch as the data source when appropriate, and **consider supporting entscheidsuche.ch if using the data commercially.**

## License

This Python client is licensed under the MIT License.

The MIT License applies only to this client code. It does not apply to Entscheidsuche data, API content, court decisions, or other source materials returned by the service. For data and content licensing details, consult [Entscheidsuche](https://entscheidsuche.ch) and the respective original data sources.
