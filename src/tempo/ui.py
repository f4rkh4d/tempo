"""Live terminal UI using rich.

`run_session` is the interactive loop. Pressing `q` quits (aborts), `p` toggles
pause, `+` adds 5 minutes. The keypress handling uses termios on POSIX and
falls back gracefully on Windows / non-tty environments (no keys, just the
countdown).

Design notes
------------
The layout is a 70×17 panel with three horizontal rows:

    1. Header — tag in bold, session count today, target duration.
    2. Big digital countdown — rendered from a 3-line block font for legibility
       across the room. Updates once per second.
    3. Footer — progress bar + status + hints.

Colors come from `_palette()` which honors `NO_COLOR` env.
"""

from __future__ import annotations

import os
import select
import sys
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from .store import Session, Store
from .timer import Timer

# ---------- keypress helpers (POSIX-only) ----------


def _try_read_key(timeout: float = 0.2) -> Optional[str]:
    """Non-blocking read of a single char from stdin.

    Returns None on timeout or non-tty. Windows returns None (fall back to
    the passive countdown — still useful, just without keyboard shortcuts).
    """
    if os.name == "nt" or not sys.stdin.isatty():
        return None
    try:
        import termios
        import tty
    except ImportError:
        return None

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if ready:
            return sys.stdin.read(1)
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ---------- color palette ----------


def _palette() -> dict:
    if os.environ.get("NO_COLOR"):
        return {
            "accent": "default",
            "accent_dim": "default",
            "text": "default",
            "text_dim": "default",
            "ok": "default",
            "warn": "default",
        }
    return {
        "accent": "color(39)",   # teal-ish cyan
        "accent_dim": "color(31)",
        "text": "color(255)",
        "text_dim": "color(245)",
        "ok": "color(78)",       # soft green
        "warn": "color(215)",    # soft amber
    }


# ---------- big digital font ----------

# 3-line tall rendering of 0-9 and ':'. Dense enough to scan across a room.
_DIGITS = {
    "0": ("██████", "██  ██", "██████"),
    "1": ("    ██", "    ██", "    ██"),
    "2": ("██████", "██████", "██████"),  # simple block
    "3": ("██████", " █████", "██████"),
    "4": ("██  ██", "██████", "    ██"),
    "5": ("██████", "██████", "██████"),
    "6": ("██████", "██  ██", "██████"),
    "7": ("██████", "    ██", "    ██"),
    "8": ("██████", "██████", "██████"),
    "9": ("██████", "██████", "    ██"),
    ":": ("      ", "  ██  ", "      "),
    " ": ("      ", "      ", "      "),
}

# Cleaner per-digit block font (one we actually want to ship — clear
# distinction between similar digits like 6/8 and 3/8/9).
_CLEAN_DIGITS = {
    "0": ("╭──╮", "│  │", "╰──╯"),
    "1": ("  ╷ ", "  │ ", "  ╵ "),
    "2": ("╶──╮", " ╭─╯", "╰── "),
    "3": ("╶──╮", " ─╮│", "╶──╯"),
    "4": ("╷  ╷", "╰──┤", "   ╵"),
    "5": ("╭── ", "╰──╮", "╶──╯"),
    "6": ("╭── ", "├──╮", "╰──╯"),
    "7": ("╶──╮", "   │", "   ╵"),
    "8": ("╭──╮", "├──┤", "╰──╯"),
    "9": ("╭──╮", "╰──┤", " ──╯"),
    ":": ("    ", " ██ ", " ██ "),
    " ": ("    ", "    ", "    "),
}


def _big_countdown(text: str) -> List[str]:
    rows = ["", "", ""]
    for ch in text:
        glyph = _CLEAN_DIGITS.get(ch, _CLEAN_DIGITS[" "])
        for i in range(3):
            sep = " " if ch != ":" else ""
            rows[i] += glyph[i] + sep
    return rows


# ---------- helpers ----------


def _format_mm_ss(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def _today_sessions_count() -> Tuple[int, int]:
    """(session_count_today, total_focus_seconds_today). Never raises."""
    try:
        store = Store()
        today = datetime.now(timezone.utc).astimezone().date()
        n = 0
        total = 0
        for s in store.all():
            try:
                started = datetime.fromisoformat(s.started_at)
            except Exception:  # noqa: BLE001
                continue
            if started.astimezone().date() != today:
                continue
            n += 1
            total += int(s.actual_sec or 0)
        return n, total
    except Exception:  # noqa: BLE001
        return 0, 0


# ---------- rendering ----------


def _render(timer: Timer, tag: str) -> Panel:
    c = _palette()
    remaining = timer.remaining
    progress = timer.progress

    # Header: tag · today's count · target duration
    tag_text = Text((tag or "focus").upper(), style=f"bold {c['accent']}")
    sessions_today, _ = _today_sessions_count()
    dot = Text(" • ", style=c["text_dim"])
    today_text = Text(
        f"today · {sessions_today + 1}{'st' if sessions_today == 0 else 'nd' if sessions_today == 1 else 'rd' if sessions_today == 2 else 'th'} session",
        style=c["text_dim"],
    )
    target_text = Text(
        f"target {_format_mm_ss(timer.total_target)}",
        style=c["text_dim"],
    )
    header = Text.assemble(tag_text, dot, today_text, dot, target_text)

    # Big countdown (3-line block)
    status_color = c["warn"] if timer.is_paused else c["accent"]
    countdown_lines = _big_countdown(_format_mm_ss(remaining))
    countdown_block = Text(
        "\n".join(countdown_lines), style=f"bold {status_color}"
    )

    # Progress bar
    bar = ProgressBar(
        total=100,
        completed=int(progress * 100),
        width=56,
        complete_style=status_color,
        finished_style=c["ok"],
        pulse_style=c["warn"],
    )

    # Status line + hints
    status_label = "paused" if timer.is_paused else "running"
    status_line = Text(
        f"{int(progress * 100)}%  •  {status_label}",
        style=f"{status_color}",
    )
    hint = Text("q quit   p pause   + add 5 min", style=c["text_dim"])

    body = Group(
        Align.center(header),
        Text(""),
        Align.center(countdown_block),
        Text(""),
        Align.center(bar),
        Text(""),
        Align.center(status_line),
        Align.center(hint),
    )
    return Panel(
        body,
        title=Text(" tempo ", style=f"bold {c['accent']}"),
        border_style=c["accent_dim"],
        padding=(1, 4),
        width=72,
    )


# ---------- public runner ----------


def run_session(timer: Timer, tag: str = "", console: Optional[Console] = None) -> str:
    """Run the live session loop. Returns 'done' or 'aborted'."""
    console = console or Console()
    timer.start()

    with Live(_render(timer, tag), console=console, refresh_per_second=6, transient=False) as live:
        while True:
            key = _try_read_key(timeout=0.2)
            if key is not None:
                k = key.lower()
                if k == "q":
                    return "aborted"
                if k == "p":
                    timer.toggle_pause()
                if k == "+":
                    timer.extend(5 * 60)

            live.update(_render(timer, tag))

            if timer.is_done:
                live.update(_render(timer, tag))
                return "done"
