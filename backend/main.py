"""
GBA+ Census Tool — backend

Two jobs only:
1. Proxy POST /api/messages to the real Anthropic API, attaching the secret
   x-api-key server-side so it's never exposed to the browser.
2. Serve the built React frontend (frontend/dist) as static files.

Run locally:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...
    uvicorn main:app --reload --port 8000
"""

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

app = FastAPI(title="GBA+ Census Tool API")


@app.get("/api/health")
async def health():
    """Diagnostic — shows whether the API key is configured."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return {
        "key_present": bool(key),
        "key_length": len(key),
        "key_prefix": key[:10] + "..." if len(key) > 10 else "(empty)",
    }


@app.post("/api/messages")
async def proxy_messages(request: Request):
    """Forward the request body to Anthropic, injecting the API key.

    Reads the key at request time (not module-load time) so Render's
    environment variable injection is always picked up correctly.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return Response(
            content='{"error":{"message":"Server is not configured with ANTHROPIC_API_KEY."}}',
            status_code=500,
            media_type="application/json",
        )

    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            upstream = await client.post(
                ANTHROPIC_URL,
                content=body,
                headers={
                    "content-type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                },
            )
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    except httpx.TimeoutException:
        return Response(
            content='{"error":{"message":"Request to Anthropic timed out after 120 seconds. Try a shorter document or reduce the analysis depth."}}',
            status_code=504,
            media_type="application/json",
        )
    except httpx.RequestError as exc:
        return Response(
            content=f'{{"error":{{"message":"Could not reach Anthropic API: {str(exc)}"}}}}',
            status_code=502,
            media_type="application/json",
        )


# ---- Serve the built frontend (frontend/dist) ----
DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")
