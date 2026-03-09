"""Audio metadata routes — health insights, cleanup, and tag editing."""
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/audio")
_executor = ThreadPoolExecutor(max_workers=2)


class TagUpdate(BaseModel):
    path: str
    artist: str | None = None
    album: str | None = None
    title: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    year: int | None = None


@router.get("/health")
async def audio_health(limit: int = 100):
    """Return audio metadata health report."""
    from ..app import get_connections
    cat_conn, _, _ = get_connections()
    from ...db.audio import get_audio_health
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: get_audio_health(cat_conn, limit))


@router.get("/cleanup")
async def audio_cleanup(limit: int = 50):
    """Return duplicate tracks and inconsistent artist names."""
    from ..app import get_connections
    cat_conn, _, _ = get_connections()
    from ...db.audio import get_audio_cleanup
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: get_audio_cleanup(cat_conn, limit))


@router.post("/update_tags")
async def update_tags(update: TagUpdate):
    """Write audio tags to a file and refresh the catalogue entry."""
    if not Path(update.path).exists():
        raise HTTPException(status_code=404, detail=f"File not found: {update.path}")

    from ..app import get_connections
    cat_conn, srch_conn, _ = get_connections()

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            _executor, lambda: _do_update_tags(update, cat_conn, srch_conn)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "path": update.path}


def _do_update_tags(update: TagUpdate, cat_conn, srch_conn) -> None:
    """Write mutagen tags, update catalog, refresh FTS. Runs in thread pool."""
    from mutagen import File as MutagenFile

    audio = MutagenFile(str(update.path), easy=True)
    if audio is None:
        raise ValueError(f"File format not supported by mutagen: {update.path}")

    if update.artist is not None:
        audio["artist"] = [update.artist]
    if update.album is not None:
        audio["album"] = [update.album]
    if update.title is not None:
        audio["title"] = [update.title]
    if update.album_artist is not None:
        audio["albumartist"] = [update.album_artist]
    if update.track_number is not None:
        audio["tracknumber"] = [str(update.track_number)]
    if update.year is not None:
        audio["date"] = [str(update.year)]

    audio.save()

    # Update catalog
    row = cat_conn.execute(
        "SELECT id FROM files WHERE path = ? AND deleted = 0", (update.path,)
    ).fetchone()
    if not row:
        return

    file_id = row["id"]
    fields = {}
    if update.artist is not None:
        fields["artist"] = update.artist
    if update.album is not None:
        fields["album"] = update.album
    if update.title is not None:
        fields["title"] = update.title
    if update.album_artist is not None:
        fields["album_artist"] = update.album_artist
    if update.track_number is not None:
        fields["track_number"] = update.track_number
    if update.year is not None:
        fields["year"] = update.year

    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        cat_conn.execute(
            f"UPDATE audio_metadata SET {set_clause} WHERE file_id = ?",
            list(fields.values()) + [file_id],
        )
        cat_conn.commit()

    # Refresh FTS
    from ...db.catalog import get_file
    from ...db.search_index import index_file
    record = get_file(cat_conn, file_id)
    if record and srch_conn:
        index_file(srch_conn, record)
        srch_conn.commit()
