"""Session aggregation: total time, per-tag breakdown, heatmaps, streaks."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from .store import Session


@dataclass
class Summary:
    """Aggregated stats for a set of sessions."""

    total_sec: int
    session_count: int
    by_tag_sec: Dict[str, int]  # ordered longest-first
    by_day_sec: Dict[date, int] = field(default_factory=dict)
    window_label: str = ""

    def format_total(self) -> str:
        return format_duration(self.total_sec)

    def bars(self, width: int = 20) -> List[Tuple[str, int, str]]:
        """Return [(tag, seconds, bar)] for display. Longest gets full width."""
        if not self.by_tag_sec:
            return []
        longest = max(self.by_tag_sec.values())
        out: List[Tuple[str, int, str]] = []
        for tag, sec in self.by_tag_sec.items():
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
    day_totals: Dict[date, int] = defaultdict(int)
    total = 0
    for s in filtered:
        seconds = int(s.actual_sec or 0)
        total += seconds
        tag_totals[s.tag or "untagged"] += seconds
        try:
            d = datetime.fromisoformat(s.started_at).astimezone().date()
            day_totals[d] += seconds
        except Exception:  # noqa: BLE001
            pass

    ordered = dict(sorted(tag_totals.items(), key=lambda kv: -kv[1]))
    ordered_days = dict(sorted(day_totals.items()))

    return Summary(
        total_sec=total,
        session_count=len(filtered),
        by_tag_sec=ordered,
        by_day_sec=ordered_days,
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


# ---------- streaks ----------


def current_streak(sessions: Iterable[Session], today: Optional[date] = None) -> int:
    """Consecutive days (ending today or yesterday) with at least one session.

    Today is optional to keep the streak alive if you haven't started yet —
    a streak counts as long as today OR yesterday had a session. Missing
    yesterday breaks it.
    """
    today = today or datetime.now(timezone.utc).astimezone().date()
    days = {
        datetime.fromisoformat(s.started_at).astimezone().date()
        for s in sessions
        if s.started_at
    }
    if not days:
        return 0

    # Grace: start counting from today OR yesterday, whichever is in the set.
    if today in days:
        cursor = today
    elif (today - timedelta(days=1)) in days:
        cursor = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def longest_streak(sessions: Iterable[Session]) -> int:
    """Longest-ever streak of consecutive days with at least one session."""
    days = sorted({
        datetime.fromisoformat(s.started_at).astimezone().date()
        for s in sessions
        if s.started_at
    })
    if not days:
        return 0
    best = 1
    current = 1
    for prev, cur in zip(days, days[1:]):
        if cur - prev == timedelta(days=1):
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


# ---------- heatmap ----------

# Five shades of green, lightest to darkest. Indexed 0 (no activity) to 4.
HEATMAP_SHADES = ["color(236)", "color(22)", "color(28)", "color(34)", "color(46)"]


def heatmap_cells(
    sessions: Iterable[Session],
    days: int = 90,
    today: Optional[date] = None,
) -> List[Tuple[date, int, int]]:
    """Return [(day, seconds, shade_index)] for the last `days` days, oldest first.

    shade_index ∈ 0..4. Thresholds are relative: 4 = 95th percentile,
    3 = 70th, 2 = 40th, 1 = any activity, 0 = none.
    """
    today = today or datetime.now(timezone.utc).astimezone().date()
    start = today - timedelta(days=days - 1)

    by_day: Dict[date, int] = defaultdict(int)
    for s in sessions:
        try:
            d = datetime.fromisoformat(s.started_at).astimezone().date()
        except Exception:  # noqa: BLE001
            continue
        if start <= d <= today:
            by_day[d] += int(s.actual_sec or 0)

    active_values = sorted(v for v in by_day.values() if v > 0)
    if active_values:
        def pct(p: float) -> float:
            idx = int(round((len(active_values) - 1) * p))
            return active_values[idx]

        thresholds = [pct(0.40), pct(0.70), pct(0.95)]
    else:
        thresholds = [0, 0, 0]

    def shade(seconds: int) -> int:
        if seconds <= 0:
            return 0
        if seconds >= thresholds[2]:
            return 4
        if seconds >= thresholds[1]:
            return 3
        if seconds >= thresholds[0]:
            return 2
        return 1

    out: List[Tuple[date, int, int]] = []
    cursor = start
    while cursor <= today:
        seconds = by_day.get(cursor, 0)
        out.append((cursor, seconds, shade(seconds)))
        cursor += timedelta(days=1)
    return out
