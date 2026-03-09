"""Top-level indexer orchestration."""
from __future__ import annotations
import logging
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..config.schema import Config
from ..db.connection import get_catalog_conn, get_search_conn
from ..db import (
    upsert_batch, mark_missing_deleted, upsert_device,
    index_batch, IndexBatch,
)
from .metadata import extract_metadata, detect_steam_workshop
from .steam import resolve_workshop_item
from .walker import build_exclusion_matcher, walk_directory

logger = logging.getLogger(__name__)

PUSH_BATCH_SIZE = 100


@dataclass
class IndexerStats:
    files_found: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    files_errored: int = 0
    files_deleted: int = 0
    duration_seconds: float = 0.0


def _needs_reindex(path: Path, existing_record) -> bool:
    """Return True if the file should be re-indexed."""
    if existing_record is None:
        return True
    try:
        stat = path.stat()
        if (
            existing_record.modified_at != stat.st_mtime
            or existing_record.size != stat.st_size
        ):
            return True
    except OSError:
        return True
    return False


def run_indexer(
    roots: list[Path],
    config: Config,
    force: bool = False,
    progress_callback=None,
) -> IndexerStats:
    stats = IndexerStats()
    start = time.time()

    catalog_conn = None
    search_conn = None

    if config.index_mode == "local":
        catalog_conn = get_catalog_conn(config.catalog_db_path)
        search_conn = get_search_conn(config.search_db_path)
        upsert_device(catalog_conn, config.device_name, platform.system())
        catalog_conn.commit()

    seen_ids: set[str] = set()
    pending_records = []

    for root in roots:
        root = root.resolve()
        if not root.exists():
            logger.warning("Index root does not exist: %s", root)
            continue

        logger.info("Indexing root: %s", root)
        exclusion_fn = build_exclusion_matcher(root, config.exclusions)

        for path in walk_directory(root, exclusion_fn):
            stats.files_found += 1
            file_id = f"{config.device_name}:{path}"
            seen_ids.add(file_id)

            try:
                existing = None
                if catalog_conn and not force:
                    from ..db.catalog import get_file
                    existing = get_file(catalog_conn, file_id)

                if not force and not _needs_reindex(path, existing):
                    stats.files_skipped += 1
                    continue

                record = extract_metadata(path, config.device_name)

                # Resolve Steam Workshop names
                if record.steam_workshop_name and catalog_conn:
                    workshop_id = record.steam_workshop_name.replace("workshop:", "")
                    resolved = resolve_workshop_item(
                        workshop_id, catalog_conn, config.steam_api_key
                    )
                    if resolved and resolved.get("resolved_name"):
                        record.steam_workshop_name = resolved["resolved_name"]

                pending_records.append(record)
                stats.files_indexed += 1

                if progress_callback:
                    progress_callback(stats)

                # Flush batch
                if len(pending_records) >= PUSH_BATCH_SIZE:
                    _flush_batch(
                        pending_records, config, catalog_conn, search_conn
                    )
                    pending_records.clear()

            except Exception as e:
                logger.error("Error indexing %s: %s", path, e)
                stats.files_errored += 1

    # Flush remaining
    if pending_records:
        _flush_batch(pending_records, config, catalog_conn, search_conn)
        pending_records.clear()

    # Mark missing files as deleted, scoped to scanned roots only
    if catalog_conn:
        deleted = mark_missing_deleted(
            catalog_conn, config.device_name, seen_ids,
            roots=[str(r.resolve()) for r in roots],
        )
        stats.files_deleted += deleted

    stats.duration_seconds = time.time() - start

    if catalog_conn:
        catalog_conn.close()
    if search_conn:
        search_conn.close()

    return stats


def _flush_batch(records, config, catalog_conn, search_conn):
    batch = IndexBatch(
        device_name=config.device_name,
        platform=platform.system(),
        records=records,
    )
    if config.index_mode == "local":
        upsert_batch(catalog_conn, batch)
        catalog_conn.commit()
        index_batch(search_conn, records)
        search_conn.commit()
    else:
        _push_batch(batch, config)


def _push_batch(batch: IndexBatch, config: Config) -> None:
    try:
        headers = {}
        if config.api_key:
            headers["X-API-Key"] = config.api_key
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{config.server_url}/index",
                json=batch.model_dump(),
                headers=headers,
            )
            resp.raise_for_status()
    except Exception as e:
        logger.error("Failed to push batch to server: %s", e)
