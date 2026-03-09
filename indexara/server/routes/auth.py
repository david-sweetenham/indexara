"""Shared authentication dependency for sensitive server endpoints."""
from __future__ import annotations
from fastapi import Header, HTTPException


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Raise 401 if an api_key is configured and the request does not supply it.

    Applied to write/sensitive endpoints (scan, open, tag editing, filesystem
    browsing) so that exposing the server on a non-loopback address does not
    leave those operations open to unauthenticated callers.
    """
    from ..app import get_connections
    _, _, config = get_connections()
    if config.api_key and x_api_key != config.api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
