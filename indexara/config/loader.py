"""Configuration loading."""
from __future__ import annotations
import os
from pathlib import Path
import yaml
from .schema import Config


_DEFAULT_CONFIG_PATH = Path.home() / ".indexara" / "config.yaml"


def load_config(path: str | Path | None = None) -> Config:
    """Load config from YAML file and environment variables."""
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    data: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

    # Map YAML keys to Config fields
    kwargs: dict = {}

    if "catalog_db_path" in data:
        kwargs["catalog_db_path"] = data["catalog_db_path"]
    if "search_db_path" in data:
        kwargs["search_db_path"] = data["search_db_path"]
    if "device_name" in data:
        kwargs["device_name"] = data["device_name"]
    if "server_url" in data:
        kwargs["server_url"] = data["server_url"]
    if "api_key" in data:
        kwargs["api_key"] = data["api_key"]
    if "anthropic_api_key" in data:
        kwargs["anthropic_api_key"] = data["anthropic_api_key"]
    if "exclude" in data:
        kwargs["exclusions"] = data["exclude"]
    if "exclusions" in data:
        kwargs["exclusions"] = data["exclusions"]
    if "steam_api_key" in data:
        kwargs["steam_api_key"] = data["steam_api_key"]
    if "mode" in data:
        kwargs["index_mode"] = data["mode"]
    if "index_mode" in data:
        kwargs["index_mode"] = data["index_mode"]
    if "log_level" in data:
        kwargs["log_level"] = data["log_level"]
    if "paths" in data:
        kwargs["index_paths"] = data["paths"]
    if "host" in data:
        kwargs["host"] = data["host"]
    if "port" in data:
        kwargs["port"] = int(data["port"])

    # Environment variable overrides (INDEXARA_ prefix)
    env_map = {
        "INDEXARA_CATALOG_DB_PATH": "catalog_db_path",
        "INDEXARA_SEARCH_DB_PATH": "search_db_path",
        "INDEXARA_DEVICE_NAME": "device_name",
        "INDEXARA_SERVER_URL": "server_url",
        "INDEXARA_API_KEY": "api_key",
        "ANTHROPIC_API_KEY": "anthropic_api_key",
        "INDEXARA_ANTHROPIC_API_KEY": "anthropic_api_key",
        "INDEXARA_STEAM_API_KEY": "steam_api_key",
        "INDEXARA_INDEX_MODE": "index_mode",
        "INDEXARA_LOG_LEVEL": "log_level",
        "INDEXARA_HOST": "host",
        "INDEXARA_PORT": "port",
    }
    for env_key, field_name in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            if field_name == "port":
                kwargs[field_name] = int(val)
            else:
                kwargs[field_name] = val

    return Config(**kwargs)
