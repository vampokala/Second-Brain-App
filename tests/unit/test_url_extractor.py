"""Unit tests for URL article extraction."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from src.core.url_extractor import UrlExtractError, extract_url


def _mock_stream_response(
    *,
    status_code: int = 200,
    body: bytes = b"<html><title>Hi</title><body><p>Hello world article</p></body></html>",
    content_type: str = "text/html; charset=utf-8",
    encoding: str = "utf-8",
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.encoding = encoding
    response.headers = {"content-type": content_type}
    response.iter_bytes.return_value = iter([body])

    def raise_for_status() -> None:
        if status_code >= 400:
            request = httpx.Request("GET", "https://example.com")
            raise httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=request,
                response=httpx.Response(status_code, request=request),
            )

    response.raise_for_status.side_effect = raise_for_status
    return response


def _patch_client(response: MagicMock) -> Iterator[None]:
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    stream_cm = MagicMock()
    stream_cm.__enter__.return_value = response
    stream_cm.__exit__.return_value = False
    client.stream.return_value = stream_cm

    with patch("src.core.url_extractor.httpx.Client", return_value=client):
        yield


def test_extract_url_returns_title_and_text_for_html() -> None:
    response = _mock_stream_response()
    with patch("src.core.url_extractor.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        stream_cm = MagicMock()
        stream_cm.__enter__.return_value = response
        stream_cm.__exit__.return_value = False
        client.stream.return_value = stream_cm

        page = extract_url("https://example.com/post")

    assert page.url == "https://example.com/post"
    assert "Hello" in page.text or page.title
    assert page.title


def test_extract_url_rejects_invalid_scheme() -> None:
    with pytest.raises(UrlExtractError, match="Invalid URL"):
        extract_url("ftp://example.com/file")


def test_extract_url_maps_http_status_to_upstream_error() -> None:
    response = _mock_stream_response(status_code=404)
    with patch("src.core.url_extractor.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        stream_cm = MagicMock()
        stream_cm.__enter__.return_value = response
        stream_cm.__exit__.return_value = False
        client.stream.return_value = stream_cm

        with pytest.raises(UrlExtractError) as excinfo:
            extract_url("https://example.com/missing")

    assert excinfo.value.upstream is True
    assert "404" in str(excinfo.value)


def test_extract_url_maps_connect_error_to_upstream_error() -> None:
    with patch("src.core.url_extractor.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.stream.side_effect = httpx.ConnectError("connection refused")

        with pytest.raises(UrlExtractError) as excinfo:
            extract_url("https://example.com")

    assert excinfo.value.upstream is True
    assert "Failed to fetch URL" in str(excinfo.value)


def test_extract_url_rejects_empty_extractable_text() -> None:
    response = _mock_stream_response(
        body=b"<html><body><script>var x=1</script></body></html>",
        content_type="text/html",
    )
    with (
        patch("src.core.url_extractor.httpx.Client") as client_cls,
        patch("src.core.url_extractor.trafilatura.extract", return_value=""),
        patch("src.core.url_extractor.trafilatura.extract_metadata", return_value=None),
    ):
        client = client_cls.return_value.__enter__.return_value
        stream_cm = MagicMock()
        stream_cm.__enter__.return_value = response
        stream_cm.__exit__.return_value = False
        client.stream.return_value = stream_cm

        with pytest.raises(UrlExtractError, match="No extractable text"):
            extract_url("https://example.com/empty")


def test_extract_url_rejects_oversized_response() -> None:
    response = _mock_stream_response()
    response.iter_bytes.return_value = iter([b"x" * (5_242_880 + 1)])
    with patch("src.core.url_extractor.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        stream_cm = MagicMock()
        stream_cm.__enter__.return_value = response
        stream_cm.__exit__.return_value = False
        client.stream.return_value = stream_cm

        with pytest.raises(UrlExtractError, match="exceeds"):
            extract_url("https://example.com/big")
