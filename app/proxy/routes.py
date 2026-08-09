from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
import requests

router = APIRouter(tags=["Proxy"])


@router.get("/proxy")
def proxy(url: str = Query(..., description="The absolute URL to fetch through the server")):
    """Fetch a remote URL server-side and return its response.

    Uses plain ``requests`` (no configured HTTP_PROXY). ``proxies={"http": None,
    "https": None}`` explicitly bypasses any ``HTTP_PROXY``/``HTTPS_PROXY`` env
    vars so the request goes out directly from the server.
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must start with http:// or https://")

    try:
        resp = requests.get(
            url,
            timeout=30,
            proxies={"http": None, "https": None},
            headers={"User-Agent": "JapLearningBackend/1.0"},
            stream=True,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch upstream: {e}")

    excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
    headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}

    body = resp.content
    return Response(content=body, status_code=resp.status_code, headers=headers)
