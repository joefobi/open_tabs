"""Normalize submitted URLs into owner-scoped source keys."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_FIELDS = {
    "fbclid",
    "gclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
}
_CREDENTIAL_FIELDS = {
    "access_token",
    "api_key",
    "auth",
    "code",
    "key",
    "password",
    "secret",
    "session",
    "token",
}


def normalize_source_url(source_url: str) -> str:
    """Normalize a source URL without merging distinct resources.

    Args:
        source_url: The HTTP(S) URL supplied by the extension.

    Returns:
        A normalized URL suitable as an owner-scoped source key.

    Raises:
        ValueError: Raised when the URL is not HTTP(S) or lacks a host.
    """

    parsed = urlsplit(source_url.strip())
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower() if parsed.hostname else ""

    if scheme not in {"http", "https"} or not hostname:
        raise ValueError("source_url must be an absolute HTTP(S) URL.")

    port = parsed.port
    include_port = port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    )
    netloc = hostname if not include_port else f"{hostname}:{port}"

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if _keeps_query_field(key)
    ]
    query = urlencode(filtered_query, doseq=True)

    return urlunsplit((scheme, netloc, parsed.path or "/", query, parsed.fragment))


def _keeps_query_field(key: str) -> bool:
    """Return whether a query field should remain in a source key.

    Args:
        key: The query parameter name.

    Returns:
        True when the field is not a known tracker or credential.
    """

    normalized = key.lower()
    if normalized.startswith(_TRACKING_PREFIXES):
        return False
    return normalized not in _TRACKING_FIELDS | _CREDENTIAL_FIELDS
