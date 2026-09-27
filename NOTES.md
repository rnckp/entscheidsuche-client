# Notes

- Keep full document IDs separate from metadata series signatures. The client preserves the requested ID as `CaseDocument.document_id`; replacing it with metadata `Signatur` can break retrieval. Canonical field mappings and accepted payload shapes are in [API-DOCUMENTATION.md](API-DOCUMENTATION.md).
- Metadata `HTML.Datei` / `PDF.Datei` paths are untrusted. Validate decoded segments before joining them to the docs endpoint; quoting alone does not prevent dot-segment traversal.
- API models use Pydantic dataclasses to preserve existing positional constructors and dataclass behavior while validating typed fields. Configuration uses a frozen Pydantic model. Open-ended source dictionaries still require deeper schema validation when their contracts are established.
- A client library should propagate errors to callers rather than configure application-wide JSON logging or log exceptions that it re-raises. Database persistence and agent telemetry are not applicable to this download client.
