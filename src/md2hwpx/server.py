"""FastAPI web service for Markdown to HWPX conversion.

Endpoints::

    GET  /              Web UI (single-page HTML).
    POST /convert       Upload a .md file and receive .hwpx back.
    POST /convert/text  Send raw Markdown text, receive .hwpx bytes.
    GET  /health        Health check.
    GET  /styles        List available style presets.

Run::

    uvicorn md2hwpx.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, Response

from md2hwpx import __version__
from md2hwpx.converter import Converter
from md2hwpx.style_manager import StyleManager

app = FastAPI(
    title="md2hwpx",
    description="Markdown to HWPX conversion service",
    version=__version__,
)

HWPX_MEDIA_TYPE = "application/hwpx+zip"


def _content_disposition(filename: str) -> str:
    """Build Content-Disposition header, RFC 5987 for non-ASCII names."""
    try:
        filename.encode("ascii")
        return f'attachment; filename="{filename}"'
    except UnicodeEncodeError:
        encoded = quote(filename)
        return f"attachment; filename*=UTF-8''{encoded}"


_STATIC_DIR = Path(__file__).parent / "static"
try:
    _INDEX_HTML = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
except FileNotFoundError:
    _INDEX_HTML = "<html><body><h1>md2hwpx</h1><p>Web UI not found.</p></body></html>"


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the web UI."""
    return HTMLResponse(content=_INDEX_HTML)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


@app.get("/styles")
async def list_styles() -> dict[str, list[str]]:
    """List available style presets."""
    return {"presets": StyleManager.PRESETS}


@app.post("/convert")
async def convert_file(
    file: UploadFile = File(...),
    style: str = Form("default"),
    encoding: str = Form("utf-8"),
) -> Response:
    """Upload a Markdown file and receive HWPX back.

    - **file**: Markdown file (.md)
    - **style**: Style preset name (default, academic, business, minimal)
    - **encoding**: Source file encoding
    """
    raw = await file.read()
    md_text = raw.decode(encoding)

    converter = Converter(style_preset=style)
    hwpx_bytes = converter.convert_text(md_text)

    filename = (file.filename or "document.md").rsplit(".", 1)[0] + ".hwpx"

    return Response(
        content=hwpx_bytes,
        media_type=HWPX_MEDIA_TYPE,
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@app.post("/convert/text")
async def convert_text(
    markdown: str = Form(...),
    style: str = Form("default"),
) -> Response:
    """Send raw Markdown text and receive HWPX bytes.

    - **markdown**: Markdown source text
    - **style**: Style preset name
    """
    converter = Converter(style_preset=style)
    hwpx_bytes = converter.convert_text(markdown)

    return Response(
        content=hwpx_bytes,
        media_type=HWPX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="document.hwpx"'},
    )
