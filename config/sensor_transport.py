"""Transport rules for requests carrying AURA sensor credentials."""
from __future__ import annotations

import ipaddress
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_sensor_api_request(request: urllib.request.Request, timeout: int):
    """Open a hub request directly, without ambient proxies or redirects."""
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirectHandler()
    )
    return opener.open(request, timeout=timeout)


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_safe_sensor_api_url(url: str) -> bool:
    """Allow HTTPS anywhere and HTTP only to a loopback development hub."""
    try:
        parsed = urlparse(url)
        # Accessing .port also rejects malformed ports.
        _ = parsed.port
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https" and bool(parsed.hostname)
        or parsed.scheme == "http" and is_loopback_host(parsed.hostname)
    ) and (
        parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and parsed.path in {"", "/"}
    )


def is_regular_nonsymlink_file(path: str | Path) -> bool:
    candidate = Path(path)
    if not candidate.is_absolute() or not candidate.is_file():
        return False
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current = current / part
        if current.is_symlink():
            return False
    return True
