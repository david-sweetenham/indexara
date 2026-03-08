"""Per-file metadata extraction."""
from __future__ import annotations
import mimetypes
import re
import time
from pathlib import Path

from ..db.models import AudioMetadata, FileRecord
from .hasher import compute_hash

MAX_TEXT_CHARS = 50_000
MAX_FILE_SIZE_FOR_HASH = 1024 * 1024 * 1024  # 1 GB

AUDIO_EXTENSIONS = {
    "flac": ("audio", "flac"),
    "alac": ("audio", "alac"),
    "m4a": ("audio", "m4a"),
    "mp3": ("audio", "mp3"),
    "ogg": ("audio", "ogg"),
    "wav": ("audio", "wav"),
    "aiff": ("audio", "aiff"),
    "aif": ("audio", "aiff"),
    "opus": ("audio", "opus"),
    "wma": ("audio", "wma"),
}

DOCUMENT_EXTENSIONS = {
    "pdf": ("document", "pdf"),
    "docx": ("document", "docx"),
    "doc": ("document", "doc"),
    "txt": ("document", "txt"),
    "md": ("document", "md"),
    "rst": ("document", "rst"),
    "epub": ("document", "epub"),
    "odt": ("document", "odt"),
    "rtf": ("document", "rtf"),
}

IMAGE_EXTENSIONS = {
    "jpg": ("image", "jpeg"),
    "jpeg": ("image", "jpeg"),
    "png": ("image", "png"),
    "gif": ("image", "gif"),
    "webp": ("image", "webp"),
    "tiff": ("image", "tiff"),
    "tif": ("image", "tiff"),
    "bmp": ("image", "bmp"),
    "svg": ("image", "svg"),
    "raw": ("image", "raw"),
    "cr2": ("image", "raw"),
    "nef": ("image", "raw"),
    "arw": ("image", "raw"),
    "dng": ("image", "raw"),
}

VIDEO_EXTENSIONS = {
    "mp4": ("video", "mp4"),
    "mkv": ("video", "mkv"),
    "avi": ("video", "avi"),
    "mov": ("video", "mov"),
    "webm": ("video", "webm"),
    "flv": ("video", "flv"),
    "wmv": ("video", "wmv"),
    "m4v": ("video", "m4v"),
}

ARCHIVE_EXTENSIONS = {
    "zip": ("archive", "zip"),
    "tar": ("archive", "tar"),
    "gz": ("archive", "gz"),
    "bz2": ("archive", "bz2"),
    "xz": ("archive", "xz"),
    "7z": ("archive", "7z"),
    "rar": ("archive", "rar"),
    "zst": ("archive", "zst"),
}

CODE_EXTENSIONS = {
    "py": ("code", "python"),
    "js": ("code", "javascript"),
    "ts": ("code", "typescript"),
    "rs": ("code", "rust"),
    "go": ("code", "go"),
    "java": ("code", "java"),
    "cpp": ("code", "cpp"),
    "c": ("code", "c"),
    "h": ("code", "c"),
    "cs": ("code", "csharp"),
    "rb": ("code", "ruby"),
    "php": ("code", "php"),
    "swift": ("code", "swift"),
    "kt": ("code", "kotlin"),
    "sh": ("code", "shell"),
    "bash": ("code", "shell"),
}

DATA_EXTENSIONS = {
    "json": ("data", "json"),
    "csv": ("data", "csv"),
    "xml": ("data", "xml"),
    "yaml": ("data", "yaml"),
    "yml": ("data", "yaml"),
    "toml": ("data", "toml"),
    "sql": ("data", "sql"),
    "db": ("data", "sqlite"),
    "sqlite": ("data", "sqlite"),
}

ALL_KNOWN = {
    **AUDIO_EXTENSIONS, **DOCUMENT_EXTENSIONS, **IMAGE_EXTENSIONS,
    **VIDEO_EXTENSIONS, **ARCHIVE_EXTENSIONS, **CODE_EXTENSIONS,
    **DATA_EXTENSIONS,
}

STEAM_WORKSHOP_RE = re.compile(r"workshop[/\\]content[/\\]\d+[/\\](\d+)", re.IGNORECASE)


def get_type_classification(extension: str) -> tuple[str, str]:
    ext = extension.lower().lstrip(".")
    return ALL_KNOWN.get(ext, ("other", ext or "unknown"))


def detect_steam_workshop(path: Path) -> str | None:
    m = STEAM_WORKSHOP_RE.search(str(path))
    return m.group(1) if m else None


def extract_audio_metadata(path: Path) -> AudioMetadata | None:
    try:
        import mutagen
        from mutagen import File as MutagenFile
        audio = MutagenFile(str(path), easy=True)
        if audio is None:
            return None

        def _get(key: str) -> str | None:
            val = audio.get(key)
            return str(val[0]) if val else None

        def _get_int(key: str) -> int | None:
            val = _get(key)
            if val is None:
                return None
            # handle "5/12" track number format
            try:
                return int(val.split("/")[0])
            except (ValueError, AttributeError):
                return None

        duration = None
        bitrate = None
        sample_rate = None
        if hasattr(audio, "info") and audio.info:
            info = audio.info
            duration = getattr(info, "length", None)
            bitrate = getattr(info, "bitrate", None)
            sample_rate = getattr(info, "sample_rate", None)

        return AudioMetadata(
            title=_get("title"),
            artist=_get("artist"),
            album=_get("album"),
            album_artist=_get("albumartist"),
            track_number=_get_int("tracknumber"),
            disc_number=_get_int("discnumber"),
            year=_get_int("date"),
            duration_seconds=duration,
            bitrate=bitrate,
            sample_rate=sample_rate,
        )
    except Exception:
        return None


def extract_text_content(path: Path, extension: str) -> str | None:
    ext = extension.lower().lstrip(".")
    try:
        if ext == "pdf":
            from pdfminer.high_level import extract_text
            text = extract_text(str(path))
            return text[:MAX_TEXT_CHARS] if text else None
        elif ext == "docx":
            import docx
            doc = docx.Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text)
            return text[:MAX_TEXT_CHARS] if text else None
        elif ext in ("txt", "md", "rst", "csv", "log", "ini", "cfg", "conf"):
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read(MAX_TEXT_CHARS)
            return text if text.strip() else None
    except Exception:
        return None
    return None


def extract_metadata(path: Path, device_name: str) -> FileRecord:
    stat = path.stat()
    ext = path.suffix.lower().lstrip(".")
    mime_type, _ = mimetypes.guess_type(str(path))
    type_group, type_subgroup = get_type_classification(ext)

    # Content hash — skip files over 1 GB
    content_hash = None
    if stat.st_size <= MAX_FILE_SIZE_FOR_HASH:
        content_hash = compute_hash(path)

    # Audio metadata
    audio_metadata = None
    if type_group == "audio":
        audio_metadata = extract_audio_metadata(path)

    # Text extraction
    text_content = None
    if type_group == "document":
        text_content = extract_text_content(path, ext)
    elif ext in ("txt", "md", "rst"):
        text_content = extract_text_content(path, ext)

    # Steam Workshop
    steam_workshop_name = None
    workshop_id = detect_steam_workshop(path)
    if workshop_id:
        steam_workshop_name = f"workshop:{workshop_id}"

    file_id = f"{device_name}:{path}"

    return FileRecord(
        id=file_id,
        device_name=device_name,
        path=str(path),
        filename=path.name,
        extension=ext or None,
        size=stat.st_size,
        created_at=stat.st_ctime,
        modified_at=stat.st_mtime,
        mime_type=mime_type,
        type_group=type_group,
        type_subgroup=type_subgroup,
        content_hash=content_hash,
        last_indexed=time.time(),
        deleted=False,
        audio_metadata=audio_metadata,
        text_content=text_content,
        steam_workshop_name=steam_workshop_name,
    )
