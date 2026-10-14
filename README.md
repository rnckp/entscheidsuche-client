# Entscheidsuche Python Client

An independent, synchronous Python client for Swiss court decisions through the
[Entscheidsuche](https://entscheidsuche.ch) endpoints.

This project is unofficial and is not affiliated with Entscheidsuche.

The [API compatibility notes](API-DOCUMENTATION.md) document implemented requests and response
mappings; they are not an official service specification.

## Installation

Requires Python 3.12 or newer and `uv`. From a local checkout, install the package and its declared
development dependencies:

```bash
cd entscheidsuche-client
uv sync
```

## Quick start

Save this example in a Python file and run it with `uv run <file>.py` from the repository root. It
makes live requests. It also writes files under `downloads/`.

```python
from entscheidsuche import EntscheidsucheClient

with EntscheidsucheClient() as client:
    results = client.search("Mietvertrag", size=10)
    for hit in results.hits:
        print(f"{hit.signatur}: {hit.date} ({hit.language})")

    if results.hits:
        hit = results.hits[0]
        saved = client.download_document(hit.spider, hit.signatur, output_dir="./downloads")
```

For more examples, see the [client guide](docs/client-guide.md) and [example
notebook](examples/entscheidsuche_demo.ipynb). Notebook API cells also make live requests; response
examples do not guarantee current service availability.

## Usage

Use a context manager or call `close()` to release the HTTP client. Instances are intended for
sequential use, with request spacing per instance. HTTP and transport errors propagate to callers.

The client covers search, JSON metadata, HTML/PDF retrieval and downloads, Index/Jobs checkpoints,
facets, blocklists, directory listings, and sitemaps. Local utilities support filtering, grouping,
statistics, and export.

Search returns one page per call. Incomplete searches raise `IncompleteSearchError`, which retains
partial results. Downloads skip HTTP 404s and overwrite matching filenames; other failures
propagate. Blocklists are not applied automatically. Static scraper lists do not establish current
coverage; use `get_facets()` for service-provided mappings.

See the [client guide](docs/client-guide.md) for method examples, response behavior, and error
handling.

## Configuration

The client loads `config.yaml` from the working directory, or a file selected with `config_path`.
Settings can be at the root or under `entscheidsuche:`. The defaults are a 30-second HTTPX timeout
and a 0.5-second interval between request starts. Constructor timing arguments override loaded
settings. `base_url`, `docs_url`, and `search_url` are independent settings. Retries are not
automatic.

See [configuration details](docs/client-guide.md#configuration) for validation, overrides, and
file-discovery behavior. The checkout includes [config.yaml](config.yaml); the working directory
controls implicit configuration and relative output paths.

## Scope and compatibility

This is a client library. It does not provide an application server or async client. Local tests use
offline fixtures or synthetic responses. They check the implemented contracts without establishing
current upstream availability or complete data coverage.

See the [API compatibility notes](API-DOCUMENTATION.md) for evidence and verification limits,
[NOTES.md](NOTES.md) for implementation decisions and historical observations, and
[PLAN.md](PLAN.md) for open tasks.

## Development

Run the local checks from the repository root:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, hooks, builds, CI, and optional checks. Agent
guidance is in [AGENTS.md](AGENTS.md).

## Responsible use

Keep request rates modest, retain source attribution and applicable reuse terms, and avoid sending
confidential or personal data to public endpoints. Consider supporting
[Entscheidsuche](https://entscheidsuche.ch), especially for commercial use.

## License

This client code is licensed under the [MIT License](LICENSE). The license does not cover data, API
content, or other source materials returned by the service. Consult
[Entscheidsuche](https://entscheidsuche.ch) and the original sources for their reuse terms.
