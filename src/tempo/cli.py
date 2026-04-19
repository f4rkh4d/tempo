"""tempo CLI entrypoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import click
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__
from .notify import notify
from .stats import (
    HEATMAP_SHADES,
    current_streak,
    format_duration,
    heatmap_cells,
    longest_streak,
    summary,
)
from .store import Session, Store, iso_now
from .timer import Timer
from .ui import run_session


@click.group(
    help="pretty pomodoro timer for the terminal. sessions, tags, heatmap, streaks.",
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


@main.command(help="show stats over a time window + calendar heatmap + streaks.")
@click.option(
    "--window",
    type=click.Choice(["day", "week", "month", "all"]),
    default="week",
    show_default=True,
)
@click.option(
    "--no-heatmap",
    is_flag=True,
    help="skip the 90-day calendar heatmap.",
)
def stats(window: str, no_heatmap: bool) -> None:
    console = Console()
    store = Store()
    all_sessions = store.all()
    summ = summary(all_sessions, window=window)

    if summ.session_count == 0 and not all_sessions:
        console.print("no sessions yet. run `tempo start` to record one.")
        return

    # Headline ----------------------------------------------------------------
    streak_now = current_streak(all_sessions)
    streak_max = longest_streak(all_sessions)

    kpi = Table.grid(padding=(0, 2))
    kpi.add_column(justify="left")
    kpi.add_row(
        _kpi("focus", summ.format_total(), "cyan"),
        _kpi("sessions", str(summ.session_count), "cyan"),
        _kpi("streak", _streak_text(streak_now), "green"),
        _kpi("best", _streak_text(streak_max), "magenta"),
    )

    console.print()
    console.print(
        Panel(
            Align.center(kpi),
            title=Text(f" {summ.window_label} ", style="bold cyan"),
            border_style="grey30",
            padding=(1, 2),
        )
    )

    # Tag breakdown -----------------------------------------------------------
    if summ.by_tag_sec:
        bars_table = Table(show_header=False, box=None, padding=(0, 2))
        bars_table.add_column("tag", style="bold")
        bars_table.add_column("dur", justify="right")
        bars_table.add_column("bar")
        for tag, seconds, bar in summ.bars(width=28):
            bars_table.add_row(tag, format_duration(seconds), f"[cyan]{bar}[/cyan]")

        console.print()
        console.print(
            Panel(bars_table, title="[bold]by tag[/bold]", border_style="grey30", padding=(1, 2))
        )

    # Heatmap -----------------------------------------------------------------
    if not no_heatmap:
        cells = heatmap_cells(all_sessions, days=90)
        console.print()
        console.print(
            Panel(
                _render_heatmap(cells),
                title="[bold]last 90 days[/bold]",
                border_style="grey30",
                padding=(1, 2),
            )
        )


def _kpi(label: str, value: str, color: str = "cyan") -> Table:
    t = Table.grid()
    t.add_column()
    t.add_row(Text(value, style=f"bold {color}"))
    t.add_row(Text(label.upper(), style="grey62"))
    return t


def _streak_text(days: int) -> str:
    return f"{days} day{'s' if days != 1 else ''}"


def _render_heatmap(cells) -> Text:
    """Render the heatmap as a 7-row grid (Mon → Sun), one column per week.

    Uses a solid foreground block (▇▇) per cell — renders reliably even when
    rich strips background colors (piped output, some terminals).
    """
    if not cells:
        return Text("no data yet.", style="grey62")

    # Group cells into columns-of-7 (weeks). First column is padded with None
    # before Monday so all columns land in the right row slot.
    weeks: list[list] = []
    for day, seconds, shade in cells:
        weekday = day.weekday()  # Mon=0 .. Sun=6
        if not weeks or len(weeks[-1]) == 7:
            column: list = []
            if not weeks:
                for _ in range(weekday):
                    column.append(None)
            weeks.append(column)
        weeks[-1].append((day, seconds, shade))

    while weeks and len(weeks[-1]) < 7:
        weeks[-1].append(None)

    labels = ["mon", "", "wed", "", "fri", "", "sun"]
    t = Text()
    for row_idx, label in enumerate(labels):
        t.append(f" {label:<3} ", style="grey62")
        for col in weeks:
            cell = col[row_idx]
            if cell is None:
                t.append("   ")
            else:
                _, _, shade = cell
                t.append("▇▇", style=HEATMAP_SHADES[shade])
                t.append(" ")
        t.append("\n")

    # Legend.
    t.append("\n     less  ")
    for shade in range(5):
        t.append("▇▇", style=HEATMAP_SHADES[shade])
        t.append(" ")
    t.append(" more")
    return t


@main.command(help="today's focus so far — quick glance.")
def today() -> None:
    console = Console()
    all_sessions = Store().all()
    today_d = datetime.now(timezone.utc).astimezone().date()

    today_sessions = []
    total = 0
    tags_sec = {}
    for s in all_sessions:
        try:
            d = datetime.fromisoformat(s.started_at).astimezone().date()
        except Exception:  # noqa: BLE001
            continue
        if d != today_d:
            continue
        today_sessions.append(s)
        total += int(s.actual_sec or 0)
        tags_sec[s.tag or "untagged"] = tags_sec.get(s.tag or "untagged", 0) + int(s.actual_sec or 0)

    if not today_sessions:
        console.print("no sessions today yet. try `tempo start`.")
        return

    streak = current_streak(all_sessions)

    kpi = Table.grid(padding=(0, 2))
    kpi.add_column()
    kpi.add_row(
        _kpi("today", format_duration(total), "cyan"),
        _kpi("sessions", str(len(today_sessions)), "cyan"),
        _kpi("streak", _streak_text(streak), "green"),
    )

    tag_table = Table(show_header=False, box=None, padding=(0, 2))
    for tag, sec in sorted(tags_sec.items(), key=lambda x: -x[1]):
        tag_table.add_row(f"[bold]{tag}[/bold]", format_duration(sec))

    console.print()
    console.print(
        Panel(
            Group(Align.center(kpi), Text(""), tag_table),
            title="[bold]today[/bold]",
            border_style="grey30",
            padding=(1, 2),
        )
    )


@main.command(help="list recent sessions.")
@click.option("--limit", "-n", default=10, show_default=True, type=int)
def ls(limit: int) -> None:
    console = Console()
    sessions = Store().recent(n=limit)
    if not sessions:
        console.print("no sessions yet. run `tempo start`.")
        return

    table = Table(show_header=True, header_style="bold", border_style="grey30")
    table.add_column("when")
    table.add_column("tag")
    table.add_column("duration", justify="right")
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
