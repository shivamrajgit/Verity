"""Safety checks for URLs and server-controlled targets."""

from __future__ import annotations

import fnmatch
import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeTargetError(ValueError):
    """Raised when a target is invalid or outside the configured safety policy."""


def validate_target_url(
    url: str,
    *,
    allow_private: bool = False,
    allowed_domains: list[str] | None = None,
) -> str:
    """Validate an HTTP(S) target and reject common SSRF targets.

    DNS is resolved before the browser is launched so obvious private, loopback,
    link-local, and reserved addresses cannot be passed to the agent. Network
    egress controls are still required for a hostile production environment,
    since DNS can change after this check.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeTargetError("Target must be an absolute http(s) URL")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeTargetError("Target URLs must not contain embedded credentials")
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeTargetError("Target URL contains an invalid port") from exc
    if port == 0:
        raise UnsafeTargetError("Target URL port must be greater than zero")

    host = parsed.hostname.rstrip(".").lower()
    if allowed_domains and not any(
        fnmatch.fnmatch(host, pattern.lower().lstrip(".")) for pattern in allowed_domains
    ):
        raise UnsafeTargetError(f"Target host '{host}' is not in the allowed domain list")

    if allow_private:
        return url

    addresses: set[str] = set()
    try:
        addresses.add(str(ipaddress.ip_address(host)))
    except ValueError:
        try:
            addresses.update(
                str(info[4][0])
                for info in socket.getaddrinfo(
                    host, port or (443 if parsed.scheme == "https" else 80)
                )
            )
        except OSError:
            # An unreachable public hostname will fail later in the browser;
            # do not turn a DNS outage into a false SSRF finding.
            addresses = set()

    for address in addresses:
        ip = ipaddress.ip_address(address)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeTargetError(f"Target resolves to a private or reserved address: {host}")

    return url
