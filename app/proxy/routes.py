import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
import requests

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
        # Reject literal IPs that are already blocked above; allow public DNS names.
    return False


@router.get("/proxy")
def proxy(
    url: str = Query(..., description="The absolute URL to fetch through the server"),
    user: CurrentUser = None,
):
    """Fetch a remote URL server-side and return its response.

    Requires authentication and refuses to reach private/loopback/link-local
    addresses (including cloud metadata endpoints) to prevent SSRF.
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must start with http:// or https://")

    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise HTTPException(status_code=400, detail="Invalid URL")
    if _is_blocked_host(host):
        raise HTTPException(status_code=400, detail="Target host is not allowed")

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
