from pathlib import Path

import httpx
import pytest

from entscheidsuche.client import EntscheidsucheClient


def test_download_document_rejects_path_traversal(tmp_path: Path) -> None:
    with EntscheidsucheClient(rate_limit_delay=0) as client:
        with pytest.raises(ValueError, match="Invalid signatur"):
            client.download_document("CH_BGE", "../escape", tmp_path, formats=["json"])


def test_download_document_raises_non_404_http_errors(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    transport = httpx.MockTransport(handler)
    with EntscheidsucheClient(rate_limit_delay=0, transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.download_document(
                "CH_BGE", "CH_BGE_001_example", tmp_path, formats=["json"]
            )


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
