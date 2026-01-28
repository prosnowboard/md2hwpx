"""Tests for the FastAPI web service."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from httpx import AsyncClient, ASGITransport
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

from md2hwpx.server import app

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_MD = FIXTURE_DIR / "sample.md"

pytestmark = pytest.mark.skipif(not _HAS_HTTPX, reason="httpx not installed")


@pytest.fixture
def client():
    """Create an async test client."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
class TestHealthEndpoint:

    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


@pytest.mark.asyncio
class TestStylesEndpoint:

    async def test_list_styles(self, client):
        resp = await client.get("/styles")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        assert "default" in data["presets"]


@pytest.mark.asyncio
class TestConvertFileEndpoint:

    async def test_convert_file_upload(self, client):
        md_content = b"# Hello\n\nWorld"
        resp = await client.post(
            "/convert",
            files={"file": ("test.md", md_content, "text/markdown")},
            data={"style": "default"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/hwpx+zip"
        assert len(resp.content) > 0

    async def test_convert_with_style(self, client):
        md_content = b"# Hello"
        resp = await client.post(
            "/convert",
            files={"file": ("test.md", md_content, "text/markdown")},
            data={"style": "academic"},
        )
        assert resp.status_code == 200

    async def test_content_disposition_header(self, client):
        md_content = b"# Hello"
        resp = await client.post(
            "/convert",
            files={"file": ("myfile.md", md_content, "text/markdown")},
        )
        assert resp.status_code == 200
        assert "myfile.hwpx" in resp.headers.get("content-disposition", "")

    async def test_convert_sample_fixture(self, client):
        if not SAMPLE_MD.exists():
            pytest.skip("sample.md fixture not found")
        md_content = SAMPLE_MD.read_bytes()
        resp = await client.post(
            "/convert",
            files={"file": ("sample.md", md_content, "text/markdown")},
        )
        assert resp.status_code == 200
        assert len(resp.content) > 0


@pytest.mark.asyncio
class TestConvertTextEndpoint:

    async def test_convert_text(self, client):
        resp = await client.post(
            "/convert/text",
            data={"markdown": "# Hello\n\nParagraph."},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/hwpx+zip"
        assert len(resp.content) > 0

    async def test_convert_text_with_style(self, client):
        resp = await client.post(
            "/convert/text",
            data={"markdown": "# Hello", "style": "business"},
        )
        assert resp.status_code == 200

    async def test_korean_text(self, client):
        resp = await client.post(
            "/convert/text",
            data={"markdown": "# 한글 제목\n\n한글 본문입니다."},
        )
        assert resp.status_code == 200
        assert len(resp.content) > 0

    async def test_table_conversion(self, client):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        resp = await client.post(
            "/convert/text",
            data={"markdown": md},
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestWebUI:

    async def test_index_returns_html(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_index_contains_key_elements(self, client):
        resp = await client.get("/")
        html = resp.text
        assert "<textarea" in html
        assert "<select" in html
        assert "<button" in html

    async def test_index_contains_fetch_call(self, client):
        resp = await client.get("/")
        html = resp.text
        assert "fetch(" in html
