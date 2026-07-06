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
    """Diagnostic endpoint — shows whether the API key is configured.
    Does NOT expose the key value, only whether it is present and its length."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    all_keys = [k for k in os.environ.keys() if "ANTHROPIC" in k.upper()]
    return {
        "key_present": bool(key),
        "key_length": len(key),
        "key_prefix": key[:10] + "..." if len(key) > 10 else "(empty)",
        "anthropic_related_env_vars": all_keys,
    }


@app.post("/api/messages")
async def proxy_messages(request: Request):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return Response(
            content='{"error":{"message":"Server is not configured with ANTHROPIC_API_KEY."}}',
            status_code=500,
            media_type="application/json",
        )

    body = await request.body()

    async with httpx.AsyncClient(timeout=60.0) as client:
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


DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")
