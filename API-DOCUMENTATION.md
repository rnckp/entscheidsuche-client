# Unofficial API and Parsing Notes

This independent client is not affiliated with entscheidsuche.ch. These notes
describe the requests and response mappings implemented in
[`client.py`](entscheidsuche/client.py) and [`models.py`](entscheidsuche/models.py),
with reduced examples based on current endpoint responses checked on 2026-10-13.
The historical upstream PDF description is not used as a contract. Offline tests
use sanitized fixtures; opt-in live tests check representative endpoints without
claiming complete collection coverage or scraper scheduling guarantees.

For installation, Python usage, configuration, and fair-use guidance, see the
[README](README.md).

## Request Paths

The built-in endpoints are `https://entscheidsuche.ch` (`base_url`),
`https://entscheidsuche.ch/docs` (`docs_url`), and
`https://entscheidsuche.ch/_search.php` (`search_url`).

| Method | Request |
| --- | --- |
| `search()`, `search_raw()` | `POST {search_url}` with a JSON query body |
| `get_document_json(spider, signatur)` | `GET {docs_url}/{signatur}.json` |
| `get_document_html()`, `get_document_pdf()` | Fetch metadata, then `GET {docs_url}/{path}` |
| `get_index(spider)` | `GET {docs_url}/Index/{spider}/last` |
| `get_jobs(spider)` | `GET {docs_url}/Jobs/{spider}/last` |
| `get_facets()` | `GET {docs_url}/Facetten.json` |
| `get_blocklist()` | `GET {docs_url}/Blockliste.json` |
| `list_documents(spider)` | `GET {docs_url}/{spider}/` |
| `get_sitemap_index()` | `GET {base_url}/sitemapindex.xml` |

Identifier arguments reject empty values, slashes, backslashes, and `.`/`..`;
they are URL-quoted when inserted into paths. The metadata request validates
`spider` but does not include it in the URL or check it against the response.

## Search

`search()` sends nonempty text as `query_string` with `default_operator: AND`.
Canton (uppercased) and `hierarchy` filters use `term` on `hierarchy`. The `spider`
filter uses `term` on `_index`, with `entscheidsuche.v2-{spider.lower()}` as observed
on the current service. Language uses
`term` on `attachment.language`. Date bounds use `range` on `date` with `gte` and
`lte`. These strings are passed through without validating date syntax or
checking codes against the static lists. A sort clause is sent only when
`sort_by` is provided. With no text or filters, the body omits `query`.

For example, `search("Mietvertrag", canton="ZH", sort_by="date")` sends this body
with the built-in defaults:

```json
{
  "size": 10,
  "from": 0,
  "query": {
    "bool": {
      "must": [{"query_string": {"query": "Mietvertrag", "default_operator": "AND"}}],
      "filter": [{"term": {"hierarchy": "ZH"}}]
    }
  },
  "sort": [{"date": {"order": "desc"}}]
}
```

`SearchResult.from_json()` retains `took`, `hits.max_score`, `hits.hits`,
`hits.total.value`, `hits.total.relation`, `timed_out`, and `_shards`. Legacy integer
counts have relation `eq`; absent relation values remain `None`. `gte` means the
count is a lower bound. Scores can be `None`. Each hit retains its `sort` array,
which can be passed to a raw query as `search_after` with compatible sorting.
Timeouts and shard failures raise `IncompleteSearchError`, with partial data in
`error.result`. `search_raw()` leaves error interpretation to the caller.

Each `SearchHit` retains `_id`, `_score`, `_index`, and `_source`. Source fields
used by public properties are validated; additional fields are retained.
Optional null hierarchy/text/attachment collections become empty collections.

| Property | Mapping |
| --- | --- |
| `signatur` | `_source.id`, then `_id`, then `_source.Signatur` |
| `court_id` | `hierarchy[1]`, or `None` |
| `spider` | Explicit `Spider`, then configured docs content directory, then known index suffix with canonical case; otherwise empty string |
| `date` | `date`, then `Datum`, otherwise empty string |
| `language` | `attachment.language`, then `Sprache`, otherwise `de` |
| `title`, `abstract` | Validated language-to-text dictionaries |
| `content_url` | `attachment.content_url` |
| `reference` | String or list normalized to a list of strings |
| `sort` | Sort values returned by Elasticsearch, or `None` |

For example, `CH_PATG` is a court ID; `CH_BPatG` is its scraper directory/index.
`get_facets()` reads the current `Facetten.json` mapping. Its `FacetNode` values
retain language labels and nested `gerichte` and `kammern` mappings; chamber
nodes can carry `spider`. `to_case_document()` converts a hit without fetching
metadata. It recognizes validated HTML/PDF paths below that hit's `docs_url`.

## Document Metadata and Content

Document method arguments named `signatur` take the full document ID, such as
`hit.signatur`. Metadata `Signatur` may instead contain a series prefix.
`get_document_json()` preserves the requested ID as `CaseDocument.document_id`.
When parsing without an explicit ID, the model tries the HTML filename stem,
then the PDF filename stem, then the metadata `id` field.

Illustrative metadata accepted by the parser:

```json
{
  "Signatur": "CH_BGE_001",
  "Spider": "CH_BGE",
  "Sprache": "de",
  "Datum": "2023-05-15",
  "HTML": {
    "Datei": "CH_BGE/CH_BGE_001_example.html",
    "URL": "https://example.org/source",
    "Checksum": "example-checksum"
  },
  "Num": ["4A_123/2023"],
  "Kopfzeile": [{"Sprachen": ["de", "fr"], "Text": "Example heading"}],
  "Meta": [{"Sprachen": ["de"], "Text": "Example metadata"}],
  "Abstract": [{"Sprachen": ["de"], "Text": "Example abstract"}],
  "Checksum": "example-checksum",
  "Zeit UTC": "2023-06-01 04:05:10"
}
```

- `HTML` and `PDF` accept a path string or an object with `Datei` and `URL`.
  `url` prefers top-level `URL`, then HTML's source URL, then PDF's.
- `Kopfzeile`, `Meta`, and `Abstract` normalize language dictionaries or
  `{Sprachen, Text}` lists to dictionaries. Plain strings use the `de` key;
  suffixed fields such as `Kopfzeilefr` are also accepted.
- `Num` accepts a string, dictionary values, or a list and normalizes to strings.
- Missing `Datum` becomes `""`; there is no synthetic fallback date. Missing
  `Sprache` becomes `de`, a client default rather than evidence of language.
- Top-level `Checksum` and `Zeit UTC` are retained as strings when present.
  The client does not verify checksums or retain per-format checksums.

HTML/PDF getters fetch metadata first and use its format path when present;
otherwise they try `{spider}/{signatur}.{format}`. Metadata paths are decoded,
validated as relative paths without traversal or URL components, then quoted.
Missing metadata or content can raise HTTP errors. Format availability is not
guaranteed. Download behavior, including skipped 404s and overwrites, is described
in the [README](README.md#document-access).

`CaseDocument.html_url`, `pdf_url`, and `json_url` use the document's `docs_url`,
passed through by the client and search-hit conversion. Standalone model parsing
defaults to the public endpoint. HTML/PDF URLs validate and quote metadata paths
using the same helper as the client getters; JSON IDs are validated and quoted.

## Index and Jobs Parsing

Current Index responses store changes in `actions`, not in `signaturen`:

```json
{
  "spider": "CH_BGer",
  "job": "446973/45/2707",
  "jobtyp": "update",
  "start_time": "2026-06-19_07:52:39",
  "time": "2026-06-19_11:30:20",
  "actions": {"CH_BGer/example-id.json": "new"},
  "signaturen": {"CH_BGer_006": {"gesamt": 10, "aktuell_neu": 1}},
  "gesamt": {"gesamt": 10, "aktuell_neu": 1}
}
```

`IndexFile` retains `actions` and maps `new`/`update`/`delete` JSON paths to full
IDs in `new_documents`, `updated_documents`, and `deleted_documents`.
`total_count` uses `gesamt.gesamt`, falling back to summed signature counts when
that summary is absent. Signature status counters are not document lists.
Malformed actions, unsafe paths, unsupported actions, and invalid counts raise
validation errors instead of silently producing empty changes.

Jobs responses store per-file statuses in `dateien`:

```json
{
  "spider": "CH_BPatG",
  "job": "446973/64/2326",
  "jobtyp": "komplett",
  "time": "2026-10-13_03:17:01",
  "dateien": {
    "CH_BPatG/example-id.json": {"status": "identisch", "last_change": "446973/64/2135"},
    "CH_BPatG/example-id.pdf": {"status": "update", "scrapedate": "2026-10-13"}
  },
  "signaturen": {"CH_PATG_001": {"gesamt": 1}},
  "lastjob": {"id": "446973/64/2325", "documents": 1, "in_elasticsearch": 1}
}
```

`jobs.files` maps scraper-relative file paths to `FileStatus` models, retaining
status, checksum, last change, scrape date and additional upstream fields.
`jobs.documents` maps full document IDs to format-to-status mappings. Each
`get_documents_by_status()` result includes an ID once if any format matches;
a document can match multiple statuses. Jobs status strings remain open-ended.
Missing `dateien` and malformed file entries are rejected.

Both models retain `job`, `start_time` and `time`; Jobs also retains `lastjob`.
The `scraper` field comes from the method argument. Index `/last` returned older
checkpoints than Jobs `/last` in the sampled service responses. Do not treat a
successful request as proof that its checkpoint is current or that no historical
changes were missed.

## Blocklist, Directory, and Sitemaps

`get_blocklist()` accepts a list of strings, an object with a `blocked` list, or a
mapping of source names to lists of strings. All mapping values must be string
lists; if `blocked` exists, only that entry is returned, otherwise the lists are
flattened. Duplicates are retained. This does not enforce exclusions elsewhere.

`list_documents()` returns sorted, unique anchor `href` values ending in `.json`,
`.html`, or `.pdf`. It does not resolve or validate the links, paginate directory
listings, or check whether files are currently indexed.

`get_sitemap_index()` returns nonempty text from XML elements whose tags end in
`loc`; it does not validate URLs or fetch child sitemaps. The repository provides
no guarantee about sitemap refresh timing or completeness.

## Validation Limits

Public models preserve existing positional dataclass constructors. Nested source
fields used by public hit properties, Index actions/counts, Jobs file statuses,
and facets are validated with Pydantic. Additional source and provenance fields
are retained where the schema is intentionally open-ended. Metadata text remains
permissively normalized. Missing decision dates and languages are not inferred
from document contents. Standalone models default to the public docs endpoint.

See `tests/fixtures/README.md` for fixture provenance and `tests/test_api_live.py`
for the opt-in live check. Remaining convenience and synchronization work is in
[PLAN.md](PLAN.md).
