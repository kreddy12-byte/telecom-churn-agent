"""DATABASE_URL classification and redaction.

Credentials never belong in logs, API responses, or exception messages. This
module is the only place that inspects a connection string so the rest of the
application can talk about "sqlite" vs "postgresql" without printing the DSN.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

# ============================================================
# 1. DATABASE CONFIGURATION
# ============================================================

_SQLITE_PREFIXES = ("sqlite:", "sqlite+")
_POSTGRES_PREFIXES = ("postgresql:", "postgresql+", "postgres:", "postgres+")

# password@ in a URL, including percent-encoded values
_PASSWORD_IN_URL = re.compile(r":([^:@/]+)@")


def database_url_backend(url: str) -> str:
    """Return ``sqlite``, ``postgresql``, or ``unknown`` for a SQLAlchemy URL."""
    lowered = (url or "").strip().lower()
    if not lowered:
        return "missing"
    if lowered.startswith(_SQLITE_PREFIXES):
        return "sqlite"
    if lowered.startswith(_POSTGRES_PREFIXES):
        return "postgresql"
    return "unknown"


def is_sqlite_url(url: str) -> bool:
    return database_url_backend(url) == "sqlite"


def is_postgresql_url(url: str) -> bool:
    return database_url_backend(url) == "postgresql"


def redact_database_url(url: str) -> str:
    """Return a log-safe form of the URL (password replaced, no secrets)."""
    raw = (url or "").strip()
    if not raw:
        return "<missing>"
    try:
        parts = urlsplit(raw)
        if parts.password:
            host = parts.hostname or ""
            port = f":{parts.port}" if parts.port else ""
            user = parts.username or ""
            netloc = f"{user}:***@{host}{port}"
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        pass
    return _PASSWORD_IN_URL.sub(r":***@", raw)


def contains_database_secret(text: str, url: str) -> bool:
    """True when ``text`` appears to include a password taken from ``url``."""
    if not text:
        return False
    try:
        password = urlsplit(url).password
    except Exception:
        password = None
    if password and password in text:
        return True
    return False
