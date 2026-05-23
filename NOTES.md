# Notes

- Live entscheidsuche.ch search hits use `_id`/`_source.id` as the full document id. Metadata JSON is available at `/docs/{document_id}.json`.
- Metadata JSON `Signatur` can be a shorter series prefix; preserve the requested full id separately as `CaseDocument.document_id`.
- Metadata `Kopfzeile`, `Meta`, and `Abstract` are currently lists of `{Sprachen, Text}` entries; `HTML` and `PDF` are objects with `Datei`, `URL`, and `Checksum`.
- `Blockliste.json` is currently a mapping from scraper/source name to lists of blocked document ids.