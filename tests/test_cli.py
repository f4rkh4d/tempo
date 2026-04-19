from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from tempo.cli import main


@pytest.fixture
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect sessions.jsonl into a temp dir for each test."""
    store_path = tmp_path / "sessions.jsonl"
    monkeypatch.setenv("TEMPO_STORE", str(store_path))
    return store_path


def test_help_works() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "pomodoro" in result.output.lower()


def test_version_works() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "tempo" in result.output


def test_ls_empty_has_helpful_message(isolated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["ls"])
    assert result.exit_code == 0
    assert "no sessions" in result.output.lower()


def test_stats_empty_message(isolated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["stats"])
    assert result.exit_code == 0
    assert "no sessions" in result.output.lower()


def test_clear_empty(isolated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["clear"])
    assert result.exit_code == 0
    assert "nothing" in result.output.lower()


def test_start_rejects_nonpositive_duration(isolated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["start", "--duration", "0"])
    assert result.exit_code != 0


def test_ls_after_seeding(isolated_store: Path) -> None:
    # Seed a session directly by writing jsonl.
    import json
    isolated_store.parent.mkdir(parents=True, exist_ok=True)
    with isolated_store.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "started_at": "2026-04-19T10:00:00+00:00",
            "ended_at": "2026-04-19T10:25:00+00:00",
            "duration_sec": 1500,
            "actual_sec": 1500,
            "tag": "code",
            "note": "",
            "status": "done",
        }) + "\n")

    runner = CliRunner()
    result = runner.invoke(main, ["ls"])
    assert result.exit_code == 0
    assert "code" in result.output


def test_stats_respects_window_choices(isolated_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["stats", "--window", "bogus"])
    assert result.exit_code != 0  # invalid choice
