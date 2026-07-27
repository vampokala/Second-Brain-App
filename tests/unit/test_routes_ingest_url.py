"""Unit tests for POST /ingest/url error mapping."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.models_ingest import IngestItemResult
from src.api.routes_ingest import router
from src.core.url_extractor import UrlExtractError


@pytest.fixture
def url_app() -> tuple[TestClient, MagicMock]:
    app = FastAPI()
    app.include_router(router)
    pipeline = MagicMock()
    pipeline.ingest_url = AsyncMock()
    app.state.ingest_pipeline = pipeline
    app.state.ingest_bus = MagicMock()
    return TestClient(app), pipeline


def test_ingest_url_returns_ingested_result(url_app: tuple[TestClient, MagicMock]) -> None:
    client, pipeline = url_app
    pipeline.ingest_url.return_value = IngestItemResult(
        path="raw/imports/example_com.md",
        status="ingested",
        chunk_count=1,
    )

    res = client.post("/ingest/url", json={"url": "https://example.com"})

    assert res.status_code == 200
    body = res.json()
    assert body["results"][0]["status"] == "ingested"
    pipeline.ingest_url.assert_awaited_once()


def test_ingest_url_maps_client_extract_error_to_400(
    url_app: tuple[TestClient, MagicMock],
) -> None:
    client, pipeline = url_app
    pipeline.ingest_url.side_effect = UrlExtractError("No extractable text from URL")

    res = client.post("/ingest/url", json={"url": "https://example.com/empty"})

    assert res.status_code == 400
    assert res.json()["detail"] == "No extractable text from URL"


def test_ingest_url_maps_upstream_error_to_502(url_app: tuple[TestClient, MagicMock]) -> None:
    client, pipeline = url_app
    pipeline.ingest_url.side_effect = UrlExtractError(
        "Remote URL returned HTTP 404",
        upstream=True,
    )

    res = client.post("/ingest/url", json={"url": "https://example.com/missing"})

    assert res.status_code == 502
    assert "404" in res.json()["detail"]


def test_ingest_url_returns_503_when_pipeline_missing() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    res = client.post("/ingest/url", json={"url": "https://example.com"})

    assert res.status_code == 503
