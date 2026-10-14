# Open tasks

Unresolved implementation, compatibility, and infrastructure work. See
[NOTES.md](NOTES.md) for established constraints and historical evidence.

- **Incomplete feature:** `ScraperInfo.from_status_line()` returns zero counts, no update time, and `unknown` status without parsing its input. Establish a status-data contract before implementing it, or deprecate it separately.
- **Synchronization:** Job IDs and timestamps are retained, but automatic freshness detection, historical Index/Jobs access, and complete reconciliation are unimplemented. See the checkpoint caveat in [API-DOCUMENTATION.md](API-DOCUMENTATION.md#index-and-jobs-parsing).
- **Repeated downloads:** With default formats and successful requests, downloading one document fetches metadata three times. Reuse metadata within each operation while preserving the behavior of skipping 404s for every format, including JSON. Responses remain buffered entirely in memory; assess streaming and size limits before supporting large downloads.
- **Automation:** Verify hosted CI, Dependabot, secret scanning/push protection, and branch protection after pushing. Require `Quality`, `Python 3.13`, and `Python 3.14` on `main`; the path-filtered dependency audit should not be required.
