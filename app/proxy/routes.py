import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ..security.auth import CurrentUser

router = APIRouter(tags=["Proxy"])

# Hosts/subnets that must never be reachable through this proxy (SSRF guard).
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# Headers that should not be blindly forwarded from the client, or that the
# proxy must manage itself.
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
    "host",
}

_CLIENT_TIMEOUT = 30.0


def _is_blocked_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if any(ip in net for net in _BLOCKED_NETWORKS):
            return True
    return False


def _validate_target(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400, detail="url must start with http:// or https://"
        )
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise HTTPException(status_code=400, detail="Invalid URL")
    if _is_blocked_host(host):
        raise HTTPException(status_code=400, detail="Target host is not allowed")
    return url


def _forward_headers(request: Request) -> dict:
    headers = {}
    for name, value in request.headers.items():
        if name.lower() in _HOP_BY_HOP:
            continue
        headers[name] = value
    headers.setdefault("User-Agent", "JapLearningBackend/1.0")
    return headers


@router.api_route(
    "/proxy",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    tags=["Proxy"],
    description="Reverse proxy to an arbitrary absolute URL. Forwards the request "
    "method, headers and body, and streams the upstream response back. "
    "Refuses private/loopback/link-local hosts (SSRF guard).",
)
async def proxy(
    request: Request,
    url: str = Query(..., description="The absolute URL to fetch through the server"),
    user: CurrentUser = None,
):
    """Proxy an arbitrary HTTP request server-side.

    Supports all common HTTP methods, forwards client headers (minus hop-by-hop
    and host) and the raw request body, then streams the upstream response
    (status, headers, body) back to the caller. Authentication is required and
    private/loopback/link-local addresses are blocked to prevent SSRF.
    """
    target = _validate_target(url)
    headers = _forward_headers(request)
    body = await request.body()

    upstream = httpx.AsyncClient(
        timeout=_CLIENT_TIMEOUT,
        follow_redirects=True,
    )

    try:
        req = upstream.build_request(
            method=request.method,
            url=target,
            headers=headers,
            content=body or None,
        )
        resp = await upstream.send(req, stream=True)

        async def stream_generator():
            try:
                # aiter_bytes decodes transport framing (chunked/gzip) for us,
                # unlike aiter_raw which yields raw, un-decoded chunks.
                async for chunk in resp.aiter_bytes():
                    yield chunk
            finally:
                # Keep the upstream connection alive until the response body is
                # fully streamed to the client, then release it.
                await resp.aclose()
                await upstream.aclose()

        response_headers = {
            k: v
            for k, v in resp.headers.items()
            if k.lower() not in _HOP_BY_HOP
        }

        return StreamingResponse(
            stream_generator(),
            status_code=resp.status_code,
            headers=response_headers,
            media_type=resp.headers.get("content-type"),
        )
    except httpx.HTTPError as e:
        await upstream.aclose()
        raise HTTPException(status_code=502, detail=f"Failed to fetch upstream: {e}")
