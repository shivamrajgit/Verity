"""URL normalization and comparison utilities."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Normalize a URL for consistent comparison.

    - Lowercases scheme and host
    - Strips trailing slash from path
    - Removes fragment (#...)
    - Sorts query parameters
    - Strips default ports (80 for http, 443 for https)

    Args:
        url: The URL to normalize.

    Returns:
        Normalized URL string.
    """
    parsed = urlparse(url)

    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Strip default ports
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Normalize path — strip trailing slash (unless it's just "/")
    path = parsed.path.rstrip("/") or "/"

    # Sort query parameters for consistent comparison
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    sorted_query = urlencode(
        sorted((k, v[0] if len(v) == 1 else v) for k, v in query_params.items()),
        doseq=True,
    )

    # Drop fragment entirely
    return urlunparse((scheme, netloc, path, parsed.params, sorted_query, ""))


def is_same_domain(url: str, base_url: str) -> bool:
    """Check if a URL belongs to the same domain as the base URL.

    Args:
        url: URL to check.
        base_url: Base URL to compare against.

    Returns:
        True if both URLs share the same domain.
    """
    url_domain = (urlparse(url).hostname or "").rstrip(".").lower()
    base_domain = (urlparse(base_url).hostname or "").rstrip(".").lower()

    return bool(url_domain) and url_domain == base_domain


def resolve_url(url: str, base_url: str) -> str:
    """Resolve a potentially relative URL against a base URL.

    Args:
        url: URL that may be relative.
        base_url: Base URL to resolve against.

    Returns:
        Absolute URL string.
    """
    from urllib.parse import urljoin

    return urljoin(base_url, url)
