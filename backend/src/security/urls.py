import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


async def is_public_http_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False

    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        return False

    resolved = {ipaddress.ip_address(item[4][0]) for item in addresses}
    return bool(resolved) and all(address.is_global for address in resolved)
