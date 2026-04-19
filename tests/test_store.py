from __future__ import annotations

import json
from pathlib import Path

import pytest

from tempo.store import Session, Store, iso_now


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(path=tmp_path / "sessions.jsonl")


def _make(**overrides) -> Session:
    defaults = dict(
        started_at="2026-04-19T10:00:00+00:00",
        ended_at="2026-04-19T10:25:00+00:00",
        duration_sec=25 * 60,
        actual_sec=25 * 60,
        tag="code",
        note="",
        status="done",
    )
    defaults.update(overrides)
    return Session(**defaults)


def test_append_creates_dir_and_file(tmp_path: Path) -> None:
    store = Store(path=tmp_path / "nested" / "dir" / "sessions.jsonl")
    store.append(_make())
    assert store.path.exists()


def test_roundtrip_single(store: Store) -> None:
    original = _make(tag="uni", actual_sec=1500)
    store.append(original)
    loaded = store.all()
    assert len(loaded) == 1
    assert loaded[0] == original


def test_all_returns_empty_if_no_file(tmp_path: Path) -> None:
    store = Store(path=tmp_path / "nope.jsonl")
    assert store.all() == []


def test_all_skips_corrupt_lines(store: Store) -> None:
    store.append(_make(tag="a"))
    # Inject a bogus line.
    with store.path.open("a", encoding="utf-8") as fh:
        fh.write("{{ not json\n")
        fh.write("\n")  # blank line
    store.append(_make(tag="b"))

    loaded = store.all()
    assert [s.tag for s in loaded] == ["a", "b"]


def test_recent_returns_newest_first(store: Store) -> None:
    for i in range(5):
        store.append(_make(tag=f"t{i}"))
    recent = store.recent(n=3)
    assert [s.tag for s in recent] == ["t4", "t3", "t2"]


def test_session_from_dict_fills_defaults() -> None:
    s = Session.from_dict({
        "started_at": "x",
        "ended_at": "y",
        "duration_sec": 60,
        "actual_sec": 60,
    })
    assert s.tag == ""
    assert s.note == ""
    assert s.status == "done"


def test_iso_now_is_parseable() -> None:
    from datetime import datetime
    s = iso_now()
    # Should parse back without raising.
    datetime.fromisoformat(s)
