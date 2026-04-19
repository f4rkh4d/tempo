"""tempo CLI entrypoints."""

from __future__ import annotations

from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .notify import notify
from .stats import format_duration, summary
from .store import Session, Store, iso_now
from .timer import Timer
from .ui import run_session


@click.group(
    help="pretty pomodoro timer for the terminal. sessions, tags, weekly stats.",
)
@click.version_option(version=__version__, prog_name="tempo")
def main() -> None:
    pass


@main.command(help="start a new focus session.")
@click.option("--tag", "-t", default="", help="tag for this session (e.g. 'uni', 'code').")
@click.option(
    "--duration",
    "-d",
    default=25,
    show_default=True,
    type=int,
    help="target duration in minutes.",
)
@click.option("--note", "-n", default="", help="optional one-liner about what you're doing.")
@click.option("--no-notify", is_flag=True, help="don't fire a desktop notification at the end.")
def start(tag: str, duration: int, note: str, no_notify: bool) -> None:
    console = Console()
    if duration <= 0:
        console.print("[red]duration must be positive.[/red]")
        raise SystemExit(2)

    started_at = iso_now()
    timer = Timer(duration_sec=duration * 60)
    status = run_session(timer, tag=tag, console=console)

    ended_at = iso_now()
    sess = Session(
        started_at=started_at,
        ended_at=ended_at,
        duration_sec=duration * 60,
        actual_sec=timer.actual_sec(),
        tag=tag,
        note=note,
        status=status,
    )
    Store().append(sess)

    duration_str = format_duration(sess.actual_sec)
    tag_suffix = f" · {tag}" if tag else ""
    if status == "done":
        console.print(
            f"\n[green]done.[/green] {duration_str} of focus{tag_suffix}."
        )
        if not no_notify:
            notify("tempo — focus done", f"{duration_str}{tag_suffix}. good work.")
    else:
        console.print(
            f"\n[yellow]aborted.[/yellow] {duration_str} logged anyway."
        )
        if not no_notify:
            notify("tempo — session aborted", f"{duration_str}{tag_suffix} logged.")


@main.command(help="show stats over a time window.")
@click.option(
    "--window",
    type=click.Choice(["day", "week", "month", "all"]),
    default="week",
    show_default=True,
)
def stats(window: str) -> None:
    console = Console()
    store = Store()
    summ = summary(store.all(), window=window)

    if summ.session_count == 0:
        console.print(f"no sessions in the {summ.window_label}.")
        return

    console.print(
        f"{summ.window_label}: [bold]{summ.format_total()}[/bold] "
        f"across {summ.session_count} session{'' if summ.session_count == 1 else 's'}."
    )
    table = Table(show_header=False, box=None, padding=(0, 1))
    for tag, seconds, bar in summ.bars(width=24):
        table.add_row(tag, format_duration(seconds), f"[cyan]{bar}[/cyan]")
    console.print(table)


@main.command(help="list recent sessions.")
@click.option("--limit", "-n", default=10, show_default=True, type=int)
def ls(limit: int) -> None:
    console = Console()
    sessions = Store().recent(n=limit)
    if not sessions:
        console.print("no sessions yet. run `tempo start`.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("when")
    table.add_column("tag")
    table.add_column("duration")
    table.add_column("status")
    for s in sessions:
        when = s.started_at[:16].replace("T", " ")
        table.add_row(
            when,
            s.tag or "—",
            format_duration(s.actual_sec),
            "[green]done[/green]" if s.status == "done" else "[yellow]aborted[/yellow]",
        )
    console.print(table)


@main.command(help="clear all recorded sessions (asks for confirmation).")
@click.option("--yes", is_flag=True, help="skip the confirmation prompt.")
def clear(yes: bool) -> None:
    console = Console()
    store = Store()
    sessions = store.all()
    if not sessions:
        console.print("nothing to clear.")
        return

    if not yes:
        click.confirm(
            f"delete {len(sessions)} session{'' if len(sessions) == 1 else 's'}?",
            abort=True,
        )

    if store.path.exists():
        store.path.unlink()
    console.print(f"[green]cleared[/green] {len(sessions)} sessions.")


if __name__ == "__main__":
    main()
