# Notes

- Live entscheidsuche.ch search hits use `_id`/`_source.id` as the full document id. Metadata JSON is available at `/docs/{document_id}.json`.
- Metadata JSON `Signatur` can be a shorter series prefix; preserve the requested full id separately as `CaseDocument.document_id`.
- Metadata `Kopfzeile`, `Meta`, and `Abstract` are currently lists of `{Sprachen, Text}` entries; `HTML` and `PDF` are objects with `Datei`, `URL`, and `Checksum`.
- `Blockliste.json` is currently a mapping from scraper/source name to lists of blocked document ids.
- Metadata `HTML.Datei` / `PDF.Datei` paths are untrusted. Validate decoded segments before joining them to the docs endpoint; quoting alone does not prevent dot-segment traversal.
- API models use Pydantic dataclasses to preserve existing positional constructors and dataclass behavior while validating typed fields. Configuration uses a frozen Pydantic model. Open-ended source dictionaries still require deeper schema validation when their contracts are established.
- A client library should propagate errors to callers rather than configure application-wide JSON logging or log exceptions that it re-raises. Database persistence and agent telemetry are not applicable to this download client.
