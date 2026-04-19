from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tempo.stats import Summary, format_duration, summary
from tempo.store import Session


def _sess(
    *, started_iso: str, actual_sec: int = 1500, tag: str = "code",
) -> Session:
    return Session(
        started_at=started_iso,
        ended_at=started_iso,
        duration_sec=actual_sec,
        actual_sec=actual_sec,
        tag=tag,
    )


def test_format_duration_seconds() -> None:
    assert format_duration(0) == "0s"
    assert format_duration(45) == "45s"


def test_format_duration_minutes() -> None:
    assert format_duration(120) == "2min"
    assert format_duration(125) == "2min 5s"


def test_format_duration_hours() -> None:
    assert format_duration(3600) == "1h 00min"
    assert format_duration(3725) == "1h 02min"
    assert format_duration(7200) == "2h 00min"


def test_summary_filters_to_week() -> None:
    now = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
    sessions = [
        _sess(started_iso=(now - timedelta(days=1)).isoformat(), tag="a"),
        _sess(started_iso=(now - timedelta(days=5)).isoformat(), tag="b"),
        _sess(started_iso=(now - timedelta(days=10)).isoformat(), tag="c"),
    ]
    s = summary(sessions, window="week", now=now)
    assert s.session_count == 2  # 'c' is outside 7d
    assert "a" in s.by_tag_sec
    assert "b" in s.by_tag_sec
    assert "c" not in s.by_tag_sec


def test_summary_all_window() -> None:
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    sessions = [
        _sess(started_iso=(now - timedelta(days=400)).isoformat(), tag="old"),
        _sess(started_iso=now.isoformat(), tag="new"),
    ]
    s = summary(sessions, window="all", now=now)
    assert s.session_count == 2


def test_summary_groups_by_tag() -> None:
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    sessions = [
        _sess(started_iso=now.isoformat(), actual_sec=1500, tag="uni"),
        _sess(started_iso=now.isoformat(), actual_sec=1500, tag="uni"),
        _sess(started_iso=now.isoformat(), actual_sec=900, tag="code"),
    ]
    s = summary(sessions, window="all", now=now)
    assert s.by_tag_sec["uni"] == 3000
    assert s.by_tag_sec["code"] == 900


def test_summary_orders_longest_first() -> None:
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    sessions = [
        _sess(started_iso=now.isoformat(), actual_sec=100, tag="a"),
        _sess(started_iso=now.isoformat(), actual_sec=500, tag="b"),
        _sess(started_iso=now.isoformat(), actual_sec=300, tag="c"),
    ]
    s = summary(sessions, window="all", now=now)
    tags_in_order = list(s.by_tag_sec.keys())
    assert tags_in_order == ["b", "c", "a"]


def test_summary_empty() -> None:
    s = summary([], window="week")
    assert s.session_count == 0
    assert s.total_sec == 0
    assert s.by_tag_sec == {}


def test_untagged_sessions_grouped() -> None:
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    sessions = [
        _sess(started_iso=now.isoformat(), tag=""),
        _sess(started_iso=now.isoformat(), tag=""),
    ]
    s = summary(sessions, window="all", now=now)
    assert s.by_tag_sec == {"untagged": 3000}


def test_summary_bars_have_at_least_one_block() -> None:
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    sessions = [
        _sess(started_iso=now.isoformat(), actual_sec=10000, tag="big"),
        _sess(started_iso=now.isoformat(), actual_sec=10, tag="tiny"),
    ]
    s = summary(sessions, window="all", now=now)
    bars = dict((t, b) for t, _, b in s.bars(width=20))
    # tiny should get at least one block even though it's 0.1% of big.
    assert len(bars["tiny"]) >= 1
    assert len(bars["big"]) == 20


def test_summary_format_total() -> None:
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    sessions = [
        _sess(started_iso=now.isoformat(), actual_sec=3725, tag="a"),
    ]
    s = summary(sessions, window="all", now=now)
    assert s.format_total() == "1h 02min"
