"""Configuration schema."""
from __future__ import annotations
import socket
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    catalog_db_path: str = str(Path.home() / ".indexara" / "catalog.db")
    search_db_path: str = str(Path.home() / ".indexara" / "search.db")
    device_name: str = field(default_factory=socket.gethostname)
    server_url: str = "http://localhost:8000"
    api_key: str | None = None
    anthropic_api_key: str | None = None
    exclusions: list[str] = field(default_factory=list)
    steam_api_key: str | None = None
    index_mode: str = "local"  # "local" or "push"
    log_level: str = "INFO"
    index_paths: list[str] = field(default_factory=list)
    host: str = "0.0.0.0"
    port: int = 8000
    # AI provider: "anthropic" (default) or "openai-compatible" (Ollama, LM Studio, etc.)
    ai_provider: str = "anthropic"
    ai_base_url: str | None = None   # e.g. http://localhost:11434/v1
    ai_model: str | None = None      # e.g. llama3.2, mistral, qwen2.5
