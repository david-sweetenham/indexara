"""Indexara CLI."""
from __future__ import annotations
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

app = typer.Typer(
    name="indexara",
    help="Indexara — personal file catalogue with AI-powered search",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


def _get_config(config_path: str | None = None):
    from ..config.loader import load_config
    return load_config(config_path)


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural language search query"),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum results"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    server: bool = typer.Option(False, "--server", "-s", help="Query via server instead of local DB"),
):
    """Search your file catalogue using natural language."""
    from .output import render_search_results

    cfg = _get_config(config)

    if server or cfg.index_mode == "push":
        _search_via_server(query, limit, cfg)
    else:
        _search_local(query, limit, cfg)


def _search_local(query: str, limit: int, cfg):
    from .output import render_search_results
    from ..db.connection import get_catalog_conn, get_search_conn
    from ..search.executor import execute_search

    cat_conn = get_catalog_conn(cfg.catalog_db_path)
    srch_conn = get_search_conn(cfg.search_db_path)

    results = execute_search(query, cat_conn, srch_conn, cfg, limit)
    render_search_results(results)


def _search_via_server(query: str, limit: int, cfg):
    from .output import render_search_results
    from ..db.models import SearchResult
    import httpx

    try:
        headers = {"X-API-Key": cfg.api_key} if cfg.api_key else {}
        resp = httpx.get(
            f"{cfg.server_url}/search",
            params={"q": query, "limit": limit},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = [SearchResult(**r) for r in data.get("results", [])]
        render_search_results(results)
    except Exception as e:
        err_console.print(f"[red]Server error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def ask(
    question: str = typer.Argument(..., help="Natural language question about your files"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    server: bool = typer.Option(False, "--server", "-s", help="Query via server"),
):
    """Ask a question about your files using AI."""
    from .output import render_ask_answer

    cfg = _get_config(config)

    if server or cfg.index_mode == "push":
        _ask_via_server(question, cfg)
    else:
        _ask_local(question, cfg)


def _ask_local(question: str, cfg):
    from .output import render_ask_answer
    from ..db.connection import get_catalog_conn, get_search_conn
    from ..search.executor import execute_ask

    cat_conn = get_catalog_conn(cfg.catalog_db_path)
    srch_conn = get_search_conn(cfg.search_db_path)

    response = execute_ask(question, cat_conn, srch_conn, cfg)
    render_ask_answer(response.answer)
    if response.sources:
        console.print(f"\n[dim]Sources: {', '.join(s.filename for s in response.sources[:5])}[/dim]")


def _ask_via_server(question: str, cfg):
    from .output import render_ask_answer
    import httpx

    try:
        headers = {"X-API-Key": cfg.api_key} if cfg.api_key else {}
        resp = httpx.get(
            f"{cfg.server_url}/ask",
            params={"q": question},
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        render_ask_answer(data.get("answer", ""))
    except Exception as e:
        err_console.print(f"[red]Server error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def index(
    roots: list[Path] = typer.Argument(None, help="Directories to index (default: config paths)"),
    push: bool = typer.Option(False, "--push", help="Push to remote server instead of local DB"),
    force: bool = typer.Option(False, "--force", "-f", help="Re-index all files regardless of mtime"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Index files from directories into the catalogue."""
    from .output import render_indexer_stats
    from ..indexer.agent import run_indexer

    cfg = _get_config(config)
    if push:
        cfg.index_mode = "push"

    if roots:
        index_paths = [r.resolve() for r in roots]
    elif cfg.index_paths:
        index_paths = [Path(p).expanduser().resolve() for p in cfg.index_paths]
    else:
        index_paths = [Path.home()]

    console.print(f"[bold]Indexing {len(index_paths)} root(s) in [{cfg.index_mode}] mode...[/bold]")
    for p in index_paths:
        console.print(f"  [dim]{p}[/dim]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing...", total=None)

        def on_progress(stats):
            progress.update(
                task,
                description=f"Indexed {stats.files_indexed} | Skipped {stats.files_skipped}",
            )

        stats = run_indexer(index_paths, cfg, force=force, progress_callback=on_progress)

    render_indexer_stats(stats)


@app.command()
def rebuild_search():
    """Rebuild the search index from the catalogue database."""
    from ..db.connection import get_catalog_conn, get_search_conn
    from ..db.search_index import rebuild_index
    from ..config.loader import load_config

    cfg = load_config()
    cat_conn = get_catalog_conn(cfg.catalog_db_path)
    srch_conn = get_search_conn(cfg.search_db_path)

    console.print("[bold]Rebuilding search index...[/bold]")
    count = rebuild_index(cat_conn, srch_conn)
    console.print(f"[green]Done. Re-indexed {count} files.[/green]")


@app.command()
def devices(
    config: Optional[str] = typer.Option(None, "--config", "-c"),
):
    """List all known devices in the catalogue."""
    from ..db.connection import get_catalog_conn
    from ..db.catalog import list_devices
    from rich.table import Table

    cfg = _get_config(config)
    cat_conn = get_catalog_conn(cfg.catalog_db_path)
    devs = list_devices(cat_conn)

    if not devs:
        console.print("[yellow]No devices found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Hostname")
    table.add_column("Platform")
    table.add_column("Last Seen")
    from datetime import datetime
    for d in devs:
        last_seen = datetime.fromtimestamp(d["last_seen"]).strftime("%Y-%m-%d %H:%M") if d.get("last_seen") else ""
        table.add_row(d["hostname"], d.get("platform", ""), last_seen)
    console.print(table)


@app.command()
def insights(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    server: bool = typer.Option(False, "--server", "-s", help="Query via server"),
    limit: int = typer.Option(20, "--limit", "-n", help="Rows per section"),
):
    """Show disk-usage insights: largest files, recent files, duplicates, folders."""
    cfg = _get_config(config)
    if server or cfg.index_mode == "push":
        _insights_via_server(cfg, limit)
    else:
        _insights_local(cfg, limit)


def _insights_local(cfg, limit: int):
    from ..db.connection import get_catalog_conn
    from ..db.insights import (
        get_largest_files, get_recent_files,
        get_duplicate_files, get_largest_folders,
    )
    from .output import render_insights

    cat_conn = get_catalog_conn(cfg.catalog_db_path)
    data = {
        "largest_files":   get_largest_files(cat_conn, limit),
        "recent_files":    get_recent_files(cat_conn, limit),
        "duplicate_files": get_duplicate_files(cat_conn, limit),
        "largest_folders": get_largest_folders(cat_conn, limit),
    }
    render_insights(data)


def _insights_via_server(cfg, limit: int):
    from .output import render_insights
    import httpx

    try:
        headers = {"X-API-Key": cfg.api_key} if cfg.api_key else {}
        resp = httpx.get(
            f"{cfg.server_url}/insights",
            params={"limit": limit},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        render_insights(resp.json())
    except Exception as e:
        err_console.print(f"[red]Server error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def serve(
    host: str = typer.Option(None, "--host", help="Bind host (default from config)"),
    port: int = typer.Option(None, "--port", "-p", help="Port (default from config)"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Start the Indexara web server."""
    import uvicorn
    from ..server.app import create_app

    cfg = _get_config(config)
    if host:
        cfg.host = host
    if port:
        cfg.port = port

    app_instance = create_app(cfg)
    console.print(f"[bold green]Indexara server starting on http://{cfg.host}:{cfg.port}[/bold green]")
    uvicorn.run(app_instance, host=cfg.host, port=cfg.port, log_level=cfg.log_level.lower())


if __name__ == "__main__":
    app()
