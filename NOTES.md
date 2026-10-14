# Implementation notes

Durable decisions, constraints, and historical observations. Public usage is in
the [client guide](docs/client-guide.md); open work is in [PLAN.md](PLAN.md).

- Packaging uses `uv_build` with `module-name = "entscheidsuche"` and `module-root = ""` to preserve the existing flat package layout. Keep `uv build --force-pep517` so builds use the declared backend range when the uv CLI bundles a newer backend.

- Required CI covers Python 3.12–3.14. A local Python 3.15 smoke test passed on macOS arm64 on 2026-10-14, but the locked `pydantic-core` needed a source build. Keep 3.15 outside required CI until eligible wheels make setup fast and reproducible; a local pass does not establish Linux compatibility.

- Keep full document IDs separate from metadata series signatures. The client preserves the requested ID as `CaseDocument.document_id`; replacing it with metadata `Signatur` can break retrieval. Canonical field mappings and accepted payload shapes are in [API-DOCUMENTATION.md](API-DOCUMENTATION.md).
- Metadata `HTML.Datei` / `PDF.Datei` paths are untrusted. Validate decoded segments before joining them to the docs endpoint; quoting alone does not prevent dot-segment traversal.
- API models use Pydantic dataclasses to preserve existing positional constructors and dataclass behavior while validating typed fields. Configuration uses a frozen Pydantic model. Search source fields used by public properties are validated before use; unknown source fields remain available.
- A client library should propagate errors to callers rather than configure application-wide JSON logging or log exceptions that it re-raises. Database persistence and agent telemetry are not applicable to this download client.
- A prior review recorded Index `/last` checkpoints months older than Jobs `/last` on 2026-10-13. The reduced fixtures retain representative checkpoint fields, but do not reproduce all sampled responses or establish current freshness. Preserve job IDs and timestamps when synchronizing; do not infer freshness from HTTP success.
- Scraper identities and court hierarchy IDs differ (e.g. `CH_BPatG` versus `CH_PATG`). Unknown scraper names must not be guessed from court IDs. Use `get_facets()` for service-provided hierarchy-to-scraper mappings.
- Returned hits/documents must carry the configured docs endpoint through conversion and URL generation, with the same path validation as client getters. `cache_dir` remains accepted only for compatibility; it performs no caching.
