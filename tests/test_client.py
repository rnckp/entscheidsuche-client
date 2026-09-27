from pathlib import Path

import httpx
import pytest

from entscheidsuche.client import EntscheidsucheClient


@pytest.mark.parametrize(
    "path",
    [
        "../private.pdf",
        "%2e%2e/private.pdf",
        "%252e%252e/private.pdf",
        "/private.pdf",
        "CH_BGE/../../private.pdf",
        "CH_BGE\\private.pdf",
        "CH_BGE/file.pdf?extra=1",
        "https://example.org/file.pdf",
    ],
)
def test_metadata_paths_cannot_escape_docs(path: str) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"PDF": {"Datei": path}})

    with (
        EntscheidsucheClient(rate_limit_delay=0, transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="document path"),
    ):
        client.get_document_pdf("CH_BGE", "doc")
    assert len(requests) == 1


def test_valid_metadata_path_is_used() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path.endswith(".json"):
            return httpx.Response(200, json={"PDF": {"Datei": "Actual_Spider/doc.pdf"}})
        return httpx.Response(200, content=b"pdf content")

    with EntscheidsucheClient(rate_limit_delay=0, transport=httpx.MockTransport(handler)) as client:
        assert client.get_document_pdf("CH_BGE", "doc") == b"pdf content"
    assert requests == ["/docs/doc.json", "/docs/Actual_Spider/doc.pdf"]


@pytest.mark.parametrize(
    "kwargs", [{"size": -1}, {"size": 10001}, {"size": True}, {"from_": -1}, {"sort_order": "bad"}]
)
def test_invalid_search_arguments_fail_before_request(kwargs: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("Invalid search must not make a request")

    with (
        EntscheidsucheClient(rate_limit_delay=0, transport=httpx.MockTransport(handler)) as client,
        pytest.raises((TypeError, ValueError)),
    ):
        client.search("", **kwargs)


@pytest.mark.parametrize("kwargs", [{"timeout": -1}, {"rate_limit_delay": float("nan")}])
def test_invalid_constructor_overrides_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        EntscheidsucheClient(**kwargs)


@pytest.mark.parametrize("payload", [None, "unavailable", {"CH_BGE": "doc"}, [12]])
def test_malformed_blocklist_is_not_reported_as_empty(payload: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        return httpx.Response(200, content=json.dumps(payload))

    with (
        EntscheidsucheClient(rate_limit_delay=0, transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError),
    ):
        client.get_blocklist()


def test_download_document_rejects_path_traversal(tmp_path: Path) -> None:
    with (
        EntscheidsucheClient(rate_limit_delay=0) as client,
        pytest.raises(ValueError, match="Invalid signatur"),
    ):
        client.download_document("CH_BGE", "../escape", tmp_path, formats=["json"])


def test_download_document_raises_non_404_http_errors(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    transport = httpx.MockTransport(handler)
    with (
        EntscheidsucheClient(rate_limit_delay=0, transport=transport) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        client.download_document("CH_BGE", "CH_BGE_001_example", tmp_path, formats=["json"])


def test_get_blocklist_flattens_live_mapping_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"CH_BGE": ["doc-a"], "ZH_Obergericht": ["doc-b", "doc-c"]},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with EntscheidsucheClient(rate_limit_delay=0, transport=transport) as client:
        assert client.get_blocklist() == ["doc-a", "doc-b", "doc-c"]
