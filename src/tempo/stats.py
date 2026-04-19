"""Session aggregation: total time, per-tag breakdown, bars."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from .store import Session


@dataclass
class Summary:
    """Aggregated stats for a set of sessions."""

    total_sec: int
    session_count: int
    by_tag_sec: Dict[str, int]  # ordered longest-first
    window_label: str

    def format_total(self) -> str:
        return format_duration(self.total_sec)

    def bars(self, width: int = 20) -> List[Tuple[str, int, str]]:
        """Return [(tag, seconds, bar)] for display. Longest gets full width."""
        if not self.by_tag_sec:
            return []
        longest = max(self.by_tag_sec.values())
        out: List[Tuple[str, int, str]] = []
        for tag, sec in self.by_tag_sec.items():
            # Round up so tiny amounts still get at least one block.
            length = max(1, round(sec / longest * width)) if longest else 0
            out.append((tag, sec, "▇" * length))
        return out


def summary(
    sessions: Iterable[Session],
    window: str = "week",
    now: Optional[datetime] = None,
) -> Summary:
    """Produce a Summary for the given window.

    `window` ∈ {"day", "week", "month", "all"}.
    """
    now = now or datetime.now(timezone.utc).astimezone()
    cutoff: Optional[datetime]
    if window == "day":
        cutoff = now - timedelta(days=1)
        label = "last 24h"
    elif window == "week":
        cutoff = now - timedelta(days=7)
        label = "last 7d"
    elif window == "month":
        cutoff = now - timedelta(days=30)
        label = "last 30d"
    else:
        cutoff = None
        label = "all time"

    filtered: List[Session] = []
    for s in sessions:
        try:
            started = datetime.fromisoformat(s.started_at)
        except Exception:  # noqa: BLE001
            continue
        if cutoff is not None and started < cutoff:
            continue
        filtered.append(s)

    tag_totals: Dict[str, int] = defaultdict(int)
    total = 0
    for s in filtered:
        # Only count sessions that actually ran.
        seconds = int(s.actual_sec or 0)
        total += seconds
        tag_totals[s.tag or "untagged"] += seconds

    # Sort by longest first.
    ordered = dict(sorted(tag_totals.items(), key=lambda kv: -kv[1]))

    return Summary(
        total_sec=total,
        session_count=len(filtered),
        by_tag_sec=ordered,
        window_label=label,
    )


def format_duration(seconds: int) -> str:
    """e.g. 3725 -> '1h 02min' ; 125 -> '2min 5s' ; 45 -> '45s'."""
    seconds = int(max(0, seconds))
    if seconds >= 3600:
        hours, rem = divmod(seconds, 3600)
        minutes = rem // 60
        return f"{hours}h {minutes:02d}min"
    if seconds >= 60:
        minutes, secs = divmod(seconds, 60)
        return f"{minutes}min {secs}s" if secs else f"{minutes}min"
    return f"{seconds}s"
