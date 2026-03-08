"""Steam Workshop API resolution."""
from __future__ import annotations
import logging
import time

import httpx

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days
STEAM_API_URL = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)


def resolve_workshop_item(
    workshop_id: str,
    catalog_conn,
    api_key: str | None = None,
) -> dict | None:
    from ..db.catalog import get_steam_workshop, upsert_steam_workshop

    cached = get_steam_workshop(catalog_conn, workshop_id)
    if cached and cached.get("last_resolved"):
        age = time.time() - cached["last_resolved"]
        if age < CACHE_TTL_SECONDS:
            return cached

    try:
        data = {"itemcount": 1, "publishedfileids[0]": workshop_id}
        if api_key:
            data["key"] = api_key
        resp = httpx.post(STEAM_API_URL, data=data, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        details = (
            result.get("response", {})
            .get("publishedfiledetails", [{}])[0]
        )
        resolved = {
            "resolved_name": details.get("title"),
            "game_name": str(details.get("creator_appid", "")),
            "description": (details.get("description") or "")[:500],
        }
        upsert_steam_workshop(catalog_conn, workshop_id, resolved)
        return resolved
    except Exception as e:
        logger.debug("Steam API error for %s: %s", workshop_id, e)
        return cached
