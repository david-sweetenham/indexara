"""Pydantic models — API contract between indexer, server, and CLI."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class AudioMetadata(BaseModel):
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    year: int | None = None
    duration_seconds: float | None = None
    bitrate: int | None = None
    sample_rate: int | None = None


class FileRecord(BaseModel):
    id: str
    device_name: str
    path: str
    filename: str
    extension: str | None = None
    size: int | None = None
    created_at: float | None = None
    modified_at: float | None = None
    mime_type: str | None = None
    type_group: str | None = None
    type_subgroup: str | None = None
    content_hash: str | None = None
    last_indexed: float = 0.0
    deleted: bool = False
    audio_metadata: AudioMetadata | None = None
    text_content: str | None = None
    steam_workshop_name: str | None = None


class IndexBatch(BaseModel):
    device_name: str
    platform: str
    records: list[FileRecord]


class SearchResult(BaseModel):
    file_id: str
    filename: str
    path: str
    device_name: str
    type_group: str | None = None
    type_subgroup: str | None = None
    size: int | None = None
    modified_at: float | None = None
    audio_metadata: AudioMetadata | None = None
    snippet: str | None = None


class QueryInterpretation(BaseModel):
    fts_query: str | None = None
    filters: dict[str, Any] = {}
    limit: int = 50
    reasoning: str | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[SearchResult] = []
