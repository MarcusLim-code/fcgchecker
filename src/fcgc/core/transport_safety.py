"""Recognize credential-bearing transport text without retaining credential values."""

import re
from urllib.parse import parse_qsl, unquote, urlsplit

_PRIVATE_KEYS = {
    "token",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "authorization",
    "auth",
    "apikey",
    "clientsecret",
    "password",
    "passwd",
    "pwd",
    "secret",
    "secretkey",
    "accesskey",
    "signature",
    "sig",
    "xamzcredential",
    "xamzsignature",
    "xamzsecuritytoken",
    "awssessiontoken",
}
_URL = re.compile(r"[a-z][a-z0-9+.-]*://[^\s<>\"']+", re.I)
_HEADER_OR_ASSIGNMENT = re.compile(
    r"\b(?:authorization|proxy-authorization|cookie|set-cookie|api[-_]?key|"
    r"access[-_]?token|refresh[-_]?token|client[-_]?secret|password|passwd|pwd)"
    r"[\"']?\s*[:=]|\bbearer\s+\S+",
    re.I,
)


def private_query(query: str) -> bool:
    for key, _ in parse_qsl(query, keep_blank_values=True):
        normalized = re.sub(r"[^a-z0-9]", "", unquote(key).casefold())
        if normalized in _PRIVATE_KEYS:
            return True
    return False


def credential_uri(uri: str) -> bool:
    try:
        parsed = urlsplit(uri)
        return (
            parsed.username is not None
            or parsed.password is not None
            or private_query(parsed.query)
            or private_query(parsed.fragment)
        )
    except ValueError:
        return True


def credential_transport_text(text: str) -> bool:
    return bool(_HEADER_OR_ASSIGNMENT.search(text)) or any(
        credential_uri(match.group()) for match in _URL.finditer(text)
    )
