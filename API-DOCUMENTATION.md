# Unofficial Entscheidsuche.ch API Notes

> **Note:** This is not the official entscheidsuche.ch documentation. This repository and Python client were developed independently and are not endorsed by, associated with, or affiliated with entscheidsuche.ch.
> These notes attempt to describe the current API shape observed from the entscheidsuche.ch website and endpoints. Any official documentation should be obtained directly from entscheidsuche.ch.

Notes for accessing Swiss court decisions from publicly reachable entscheidsuche.ch endpoints.

**Base URL:** `https://entscheidsuche.ch`

## Fair Use Policy

- Be kind to the server and avoid excessive load
- Use rate limiting (recommended: 0.5s delay between requests)
- Mention entscheidsuche.ch as your source
- Consider supporting with a donation if using commercially

---

## 1. Core Concepts

### Scrapers/Spiders

Documents are collected by automated scrapers that:

- Perform **partial scans daily** (updates only)
- Perform **full scans monthly** (complete collection)
- Each scraper covers a specific court or jurisdiction

**View scrapers:** `https://entscheidsuche.ch/status`

### Naming Convention

- **Spider:** Court identifier (e.g., `CH_BGE`, `ZH_Obergericht`)
- **Signatur:** Unique document ID within a spider
- **Hierarchy:** Nested structure: `[Canton, Spider, Signatur]` (e.g., `["ZH", "ZH_Obergericht", "ZH_OG_001_123"]`)

### Cantons

All 26 Swiss cantons plus federal level (`CH`) are supported:

**Federal:** CH (Bund)  
**Cantons:** AG, AI, AR, BE, BL, BS, FR, GE, GL, GR, JU, LU, NE, NW, OW, SG, SH, SO, SZ, TG, TI, UR, VD, VS, ZG, ZH

### Known Scrapers

**Federal Courts:**

- `CH_BGE` - Bundesgericht (Federal Supreme Court)
- `CH_BVGer` - Bundesverwaltungsgericht (Federal Administrative Court)
- `CH_BPatG` - Bundespatentgericht (Federal Patent Court)

**Cantonal Courts:**

- Pattern: `{CANTON}_{COURT}` (e.g., `ZH_Obergericht`, `BE_Verwaltungsgericht`)
- Special: `XX_Upload` - Manually uploaded documents

**View status:** `https://entscheidsuche.ch/status`

---

## 2. Search API (Elasticsearch)

**Endpoint:** `POST https://entscheidsuche.ch/_search.php`  
**Format:** Elasticsearch Query DSL

### Standard Search

```json
{
  "size": 10,
  "from": 0,
  "query": {
    "bool": {
      "must": [
        {
          "query_string": {
            "query": "Mietvertrag",
            "default_operator": "AND"
          }
        }
      ],
      "filter": [
        { "term": { "hierarchy": "ZH" } },
        { "term": { "attachment.language": "de" } },
        { "range": { "date": { "gte": "2023-01-01", "lte": "2023-12-31" } } }
      ]
    }
  },
  "sort": [{ "date": { "order": "desc" } }]
}
```

### Filters

| Field                 | Type  | Description                | Example                 |
| --------------------- | ----- | -------------------------- | ----------------------- |
| `hierarchy`           | term  | Filter by canton or spider | `"ZH"`, `"CH_BGE"`      |
| `attachment.language` | term  | Document language          | `"de"`, `"fr"`, `"it"`  |
| `date`                | range | Decision/publication date  | `{"gte": "2023-01-01"}` |

### Response Structure

```json
{
  "took": 5,
  "hits": {
    "total": { "value": 100 },
    "max_score": 1.5,
    "hits": [
      {
        "_id": "CH_BGE_001_123",
        "_score": 1.5,
        "_index": "entscheidsuche.v2-ch_bge",
        "_source": {
          "date": "2023-05-15",
          "hierarchy": ["CH", "CH_BGE", "CH_BGE_001"],
          "id": "CH_BGE_001_123",
          "attachment": {
            "language": "de",
            "content_url": "https://entscheidsuche.ch/docs/CH_BGE/CH_BGE_001_123.html"
          },
          "reference": ["4A_123/2023"],
          "title": { "de": "...", "fr": "..." },
          "abstract": { "de": "...", "fr": "..." },
          "meta": { "de": "...", "fr": "..." },
          "canton": "CH",
          "scrapedate": "2026-05-23"
        }
      }
    ]
  }
}
```

---

## 3. Document Access

### Document URLs

Metadata is available via the shortcut URL:

`https://entscheidsuche.ch/docs/{document_id}.json`

HTML and PDF content paths are published in the metadata `HTML.Datei` and `PDF.Datei` fields. Search hits also expose the current content file in `attachment.content_url`.

**Formats:**

- `.json` - Metadata (always available)
- `.html` - HTML content (if available)
- `.pdf` - PDF file (if available)

### JSON Metadata Structure

```json
{
  "Signatur": "CH_BGE_001",
  "Spider": "CH_BGE",
  "Sprache": "de",
  "Datum": "2023-05-15",
  "HTML": {
    "Datei": "CH_BGE/CH_BGE_001_123_456.html",
    "URL": "https://www.bger.ch/...",
    "Checksum": "abc123..."
  },
  "PDF": {
    "Datei": "CH_BGE/CH_BGE_001_123_456.pdf",
    "URL": "https://www.bger.ch/...",
    "Checksum": "def456..."
  },
  "Num": ["4A_123/2023"],
  "Kopfzeile": [{ "Sprachen": ["de", "fr"], "Text": "..." }],
  "Meta": [{ "Sprachen": ["de"], "Text": "..." }],
  "Abstract": [{ "Sprachen": ["de"], "Text": "..." }],
  "Checksum": "abc123...",
  "Zeit UTC": "2023-06-01 04:05:10"
}
```

**Fields:**

- `Signatur` - Series/signature prefix; the full document identifier is the `{document_id}` used in the metadata URL and content filename
- `Spider` - Scraper/source name
- `Sprache` - Detected language (`de`, `fr`, `it`) - automated detection
- `Datum` - Decision/publication date (defaults to `2021-01-01` if unavailable)
- `HTML`/`PDF` - Objects containing `Datei` (relative path below `/docs`), `URL` (source URL), and `Checksum`
- `Num` - Case number(s) (may be missing or use placeholder)
- `Kopfzeile` - Metadata collection as multilingual `{Sprachen, Text}` entries
- `Meta` - Signature metadata as multilingual `{Sprachen, Text}` entries
- `Abstract` - Summary/title as multilingual `{Sprachen, Text}` entries, not always available
- `Checksum` - File integrity check (unreliable for HTML)
- `Zeit UTC` - Scraper run timestamp

---

## 4. Index and Jobs Files

Track scraper runs and document changes.

### Index Files

**Endpoint:** `https://entscheidsuche.ch/docs/Index/{spider}/last`  
**Alternative:** `https://entscheidsuche.ch/docs/Index/{spider}/{timestamp}_{jobid}.json`

**Contains:** Only updates (new, modified, deleted documents)

```json
{
  "spider": "CH_BGE",
  "job": "446973/47/2924",
  "jobtyp": "komplett",
  "start_time": "2023-06-01_05:20:15",
  "time": "2023-06-01_05:30:15",
  "gesamt": 21259,
  "signaturen": {
    "CH_BGE_001": {
      "gesamt": 172,
      "new": ["CH_BGE_001_123", "CH_BGE_001_124"],
      "update": ["CH_BGE_001_100"],
      "delete": ["CH_BGE_001_099"]
    }
  }
}
```

**Job Types:**

- `komplett` - Complete scraper run
- `update` - Incremental (recent documents only)
- `neu` - Collection reset after programmatic changes
- `unvollständig` - Incomplete run (likely error)

### Jobs Files

**Endpoint:** `https://entscheidsuche.ch/docs/Jobs/{spider}/last`

**Contains:** All documents with their status (complete list)

```json
{
  "spider": "CH_BGE",
  "job": "446973/47/2924",
  "jobtyp": "komplett",
  "start_time": "2023-06-01_05:20:15",
  "time": "2023-06-01_05:30:15",
  "gesamt": 21259,
  "signaturen": {
    "CH_BGE_001_123": {
      "json": "neu",
      "html": "identisch",
      "pdf": { "status": "update", "last_change": "178_3_100" }
    }
  }
}
```

**Document Statuses:**

- `neu` - New document
- `identisch` - No changes (references last change job ID)
- `update` - Modified but same metadata
- `nicht_mehr_da` - Document removed
- `identisch_wieder_da` - Reappeared without changes
- `anders_wieder_da` - Reappeared with modifications

---

## 5. Additional Endpoints

### Directory Listing

**Endpoint:** `https://entscheidsuche.ch/docs/{spider}/`

Returns HTML directory listing of all documents.

**Warning:** May include outdated files not in search index. Missing index file means changes could be missed.

### Blocklist

**Endpoint:** `https://entscheidsuche.ch/docs/Blockliste.json`

```json
{
  "CH_BGE": ["CH_BGE_001_999"],
  "ZH_Obergericht": ["ZH_OG_002_888"]
}
```

Mapping from scraper/source names to document names (without extension) that have been blocked/removed.

### Sitemap

**Endpoint:** `https://entscheidsuche.ch/sitemapindex.xml`

Root sitemap index (updated with each scraper run). Spider sitemaps may be split into multiple files due to size restrictions.

---

## 6. Python Client

### Installation

```bash
uv add git+https://github.com/rnckp/entscheidsuche.git
```

### Basic Usage

```python
from entscheidsuche import EntscheidsucheClient

# Create client with rate limiting
client = EntscheidsucheClient(rate_limit_delay=0.5)

# Search
results = client.search(
    query="Mietvertrag",
    size=20,
    canton="ZH",
    language="de",
    date_from="2023-01-01",
    date_to="2023-12-31",
)

# Get documents
doc = client.get_document_json("CH_BGE", "CH_BGE_001_BGE-86-I-226_1960-10-20")
html = client.get_document_html("CH_BGE", "CH_BGE_001_BGE-86-I-226_1960-10-20")
pdf = client.get_document_pdf("CH_BGE", "CH_BGE_001_BGE-86-I-226_1960-10-20")

# Download all formats
client.download_document("CH_BGE", "CH_BGE_001_BGE-86-I-226_1960-10-20", output_dir="./downloads")

# Index and jobs
index = client.get_index("CH_BGE")
jobs = client.get_jobs("CH_BGE")
blocked = client.get_blocklist()

# Utilities
scrapers = EntscheidsucheClient.list_scrapers()
cantons = EntscheidsucheClient.list_cantons()
canton_name = EntscheidsucheClient.get_canton_name("ZH")  # "Zürich"
```

### Raw Elasticsearch Query

```python
query_body = {
    "size": 100,
    "query": {
        "bool": {
            "must": [{"match": {"attachment.content": "Arbeitsgericht"}}],
            "filter": [{"term": {"hierarchy": "ZH"}}],
        }
    },
    "aggs": {"by_year": {"date_histogram": {"field": "date", "calendar_interval": "year"}}},
}

response = client.search_raw(query_body)
```

---

## Appendix: Canton Codes

| Code   | Canton                 | Code | Canton       |
| ------ | ---------------------- | ---- | ------------ |
| AG     | Aargau                 | NW   | Nidwalden    |
| AI     | Appenzell Innerrhoden  | OW   | Obwalden     |
| AR     | Appenzell Ausserrhoden | SG   | St. Gallen   |
| BE     | Bern                   | SH   | Schaffhausen |
| BL     | Basel-Land             | SO   | Solothurn    |
| BS     | Basel-Stadt            | SZ   | Schwyz       |
| FR     | Freiburg               | TG   | Thurgau      |
| GE     | Genf                   | TI   | Tessin       |
| GL     | Glarus                 | UR   | Uri          |
| GR     | Graubünden             | VD   | Waadt        |
| JU     | Jura                   | VS   | Wallis       |
| LU     | Luzern                 | ZG   | Zug          |
| NE     | Neuenburg              | ZH   | Zürich       |
| **CH** | **Bund (Federal)**     |      |              |
