"""Rich rendering utilities."""
from __future__ import annotations
from datetime import datetime

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich import box

from ..db.models import SearchResult
from ..indexer.agent import IndexerStats

console = Console()


def render_search_results(results: list[SearchResult]) -> None:
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold dim")
    table.add_column("#", style="dim", width=4)
    table.add_column("Filename", style="bold")
    table.add_column("Path", style="dim", overflow="fold", max_width=60)
    table.add_column("Device", style="cyan", width=12)
    table.add_column("Type", width=10)
    table.add_column("Size", width=8, justify="right")
    table.add_column("Modified", width=12)

    for i, r in enumerate(results, 1):
        size_str = _format_size(r.size) if r.size else ""
        modified_str = (
            datetime.fromtimestamp(r.modified_at).strftime("%Y-%m-%d")
            if r.modified_at else ""
        )
        type_str = f"{r.type_group}/{r.type_subgroup}" if r.type_subgroup else (r.type_group or "")
        table.add_row(
            str(i),
            r.filename,
            r.path,
            r.device_name,
            type_str,
            size_str,
            modified_str,
        )
    console.print(table)


def render_ask_answer(answer: str) -> None:
    console.print(Markdown(answer))


def render_indexer_stats(stats: IndexerStats) -> None:
    console.print(
        f"\n[bold green]Indexing complete[/bold green] in {stats.duration_seconds:.1f}s\n"
        f"  Found:   {stats.files_found}\n"
        f"  Indexed: {stats.files_indexed}\n"
        f"  Skipped: {stats.files_skipped}\n"
        f"  Deleted: {stats.files_deleted}\n"
        f"  Errors:  {stats.files_errored}"
    )


def render_insights(data: dict) -> None:
    """Print all four insight sections with Rich formatting."""
    # --- Largest Files ---
    console.print("\n[bold cyan]Largest Files[/bold cyan]")
    lf = data.get("largest_files", [])
    if lf:
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("Size", style="yellow", justify="right", width=10)
        t.add_column("Path", style="dim", overflow="fold")
        for row in lf:
            t.add_row(_format_size(row["size"] or 0), row["path"])
        console.print(t)
    else:
        console.print("  [dim]No data[/dim]")

    # --- Recently Added ---
    console.print("\n[bold cyan]Recently Added[/bold cyan]")
    rf = data.get("recent_files", [])
    if rf:
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("Date", style="yellow", width=12)
        t.add_column("Filename", style="bold", width=30)
        t.add_column("Path", style="dim", overflow="fold")
        for row in rf:
            date_str = (
                datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d")
                if row.get("created_at") else ""
            )
            t.add_row(date_str, row["filename"], row["path"])
        console.print(t)
    else:
        console.print("  [dim]No data[/dim]")

    # --- Duplicate Files ---
    console.print("\n[bold cyan]Duplicate Files[/bold cyan]")
    dups = data.get("duplicate_files", [])
    if dups:
        for dup in dups:
            wasted = _format_size(dup.get("wasted_bytes") or 0)
            console.print(
                f"  [yellow]{dup['copies']} copies[/yellow]  "
                f"[dim]hash {dup['content_hash'][:12]}…[/dim]  "
                f"[red]~{wasted} wasted[/red]"
            )
            for f in dup.get("files", []):
                console.print(f"    [dim]{f['path']}[/dim]")
    else:
        console.print("  [dim]No duplicates found[/dim]")

    # --- Largest Folders ---
    console.print("\n[bold cyan]Largest Folders[/bold cyan]")
    folders = data.get("largest_folders", [])
    if folders:
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("Size", style="yellow", justify="right", width=10)
        t.add_column("Files", style="dim", justify="right", width=7)
        t.add_column("Folder", style="dim", overflow="fold")
        for row in folders:
            t.add_row(
                _format_size(row["total_size"] or 0),
                str(row["file_count"]),
                row["folder"],
            )
        console.print(t)
    else:
        console.print("  [dim]No data[/dim]")

    console.print()


def _format_size(bytes: int) -> str:
    if bytes < 1024:
        return f"{bytes}B"
    if bytes < 1024 * 1024:
        return f"{bytes / 1024:.1f}K"
    if bytes < 1024 * 1024 * 1024:
        return f"{bytes / 1024 / 1024:.1f}M"
    return f"{bytes / 1024 / 1024 / 1024:.2f}G"
