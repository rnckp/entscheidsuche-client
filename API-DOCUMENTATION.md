# Unofficial API and Parsing Notes

This independent client is not affiliated with entscheidsuche.ch. These notes
describe the requests and response mappings implemented in
[`client.py`](entscheidsuche/client.py) and [`models.py`](entscheidsuche/models.py),
with illustrative payloads. They are not an upstream API specification. Local
tests establish parser behavior, not current service compatibility, collection
completeness, scraper schedules, or status semantics. Those remain unverified.

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
| `get_blocklist()` | `GET {docs_url}/Blockliste.json` |
| `list_documents(spider)` | `GET {docs_url}/{spider}/` |
| `get_sitemap_index()` | `GET {base_url}/sitemapindex.xml` |

Identifier arguments reject empty values, slashes, backslashes, and `.`/`..`;
they are URL-quoted when inserted into paths. The metadata request validates
`spider` but does not include it in the URL or check it against the response.

## Search

`search()` sends nonempty text as `query_string` with `default_operator: AND`.
Canton (uppercased) and spider filters use `term` on `hierarchy`; language uses
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

`SearchResult.from_json()` reads `took`, `hits.max_score`, `hits.hits`, and
`hits.total` (an integer or an object with `value`). It discards `total.relation`;
the resulting count is not necessarily an exact total. Scores can be `None`.
Raw queries and responses pass through `search_raw()` without model conversion.

Each `SearchHit` retains `_id`, `_score`, `_index`, and the open-ended `_source`:

| Property | Mapping |
| --- | --- |
| `signatur` | `_source.id`, then `_id`, then `_source.Signatur` |
| `spider` | `hierarchy[1]`; otherwise an uppercased index suffix, then `Spider` |
| `date` | `date`, then `Datum`, otherwise empty string |
| `language` | `attachment.language`, then `Sprache`, otherwise `de` |
| `title`, `abstract` | Corresponding source values; default empty dictionaries |
| `content_url` | `attachment.content_url`, if attachment is a dictionary |
| `reference` | `reference` normalized from a string or list to a list of strings |

The client treats `hierarchy` as a sequence whose second entry identifies a
source; that value need not match the content directory. For example, the test
fixture uses `AG_BG` in the hierarchy and `AG_Baugesetzgebung` in the content path.
`to_case_document()` converts fields already in a hit without fetching metadata.
It recognizes HTML/PDF paths only below the built-in docs URL.

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

`CaseDocument.html_url`, `pdf_url`, and `json_url` use the built-in docs endpoint,
not the client's custom configuration. They construct strings without the path
validation used by the client getters.

## Index and Jobs Parsing

`IndexFile.from_json()` expects `signaturen` entries such as:

```json
{
  "jobtyp": "komplett",
  "time": "2023-06-01_05:30:15",
  "signaturen": {
    "CH_BGE_001": {
      "gesamt": 2,
      "new": ["document-a"],
      "update": ["document-b"],
      "delete": []
    }
  }
}
```

It sums per-entry `gesamt` values (or integer entries) into `total_count` and
concatenates the `new`, `update`, and `delete` lists. It ignores a top-level
`gesamt`. `scraper` comes from the method argument, not the response.

`JobsFile.from_json()` maps `signaturen` directly to `documents`. The status
helper accepts per-format strings or objects containing `status`, as tested by:

```json
{
  "signaturen": {
    "document-a": {"json": "neu", "pdf": {"status": "update"}},
    "document-b": {"json": "identisch"}
  }
}
```

`get_documents_by_status("neu")` returns each matching document key once if any
format matches. Status and `jobtyp` values are not enums and their upstream
semantics are not validated. Both models default missing `jobtyp` to `unknown`
and `time` to an empty string. Live Jobs compatibility remains unverified; the
local fixture is evidence of parser behavior only.

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

Models are Pydantic dataclasses with typed fields, but nested search `_source`
and index/job dictionaries remain partly open-ended. Some metadata fields are
normalized permissively. Malformed nested values can still fail later or be
misinterpreted; see [PLAN.md](PLAN.md) for unresolved contract work.
