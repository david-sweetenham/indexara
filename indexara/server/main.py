"""Server entry point."""
from __future__ import annotations
import logging

import uvicorn

from ..config.loader import load_config
from .app import create_app

logging.basicConfig(level=logging.INFO)


def main():
    config = load_config()
    app = create_app(config)
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
