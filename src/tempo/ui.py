"""Live terminal UI using rich.

`run_session` is the interactive loop. Pressing `q` quits (aborts), `p` toggles
pause, `+` adds 5 minutes. The keypress handling uses termios on POSIX and
falls back gracefully on Windows / non-tty environments (no keys, just the
countdown).
"""

from __future__ import annotations

import os
import select
import sys
from typing import Optional

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.text import Text

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


# ---------- rendering ----------


def _format_mm_ss(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def _render(timer: Timer, tag: str) -> Panel:
    remaining = timer.remaining
    progress = timer.progress
    bar = ProgressBar(total=100, completed=int(progress * 100), width=36)

    tag_line = Text(tag or "focus", style="bold")
    clock_line = Text(_format_mm_ss(timer.total_target), style="dim")
    header = Text.assemble(tag_line, "  ·  ", clock_line)

    status = "paused" if timer.is_paused else "running"
    status_style = "yellow" if timer.is_paused else "cyan"
    remaining_line = Text(
        f"{_format_mm_ss(remaining)} left", style=status_style,
    )

    hint = Text("q quit · p pause · + add 5 min", style="dim")

    body = Group(
        Align.center(header),
        Text(""),
        Align.center(bar),
        Text(""),
        Align.center(remaining_line),
        Text(""),
        Align.center(hint),
        Text(""),
        Align.center(Text(f"[{status}]", style=f"dim {status_style}")),
    )
    return Panel(body, title="focus session", border_style="cyan", padding=(1, 4), width=52)


# ---------- public runner ----------


def run_session(timer: Timer, tag: str = "", console: Optional[Console] = None) -> str:
    """Run the live session loop. Returns 'done' or 'aborted'.

    Drives `timer`: polls once per ~200ms for a keypress, re-renders.
    """
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
                # one final frame so the user sees 00:00
                live.update(_render(timer, tag))
                return "done"
