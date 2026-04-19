"""jsonl-backed session store at ~/.tempo/sessions.jsonl."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class Session:
    """One completed (or aborted) focus block."""

    started_at: str
    ended_at: str
    duration_sec: int  # target duration
    actual_sec: int  # real duration (subtract pauses, add extensions)
    tag: str = ""
    note: str = ""
    status: str = "done"  # done | aborted

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        return cls(
            started_at=d["started_at"],
            ended_at=d["ended_at"],
            duration_sec=int(d["duration_sec"]),
            actual_sec=int(d["actual_sec"]),
            tag=d.get("tag", "") or "",
            note=d.get("note", "") or "",
            status=d.get("status", "done"),
        )


class Store:
    """Append-only jsonl store. One session per line."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or default_path()

    def append(self, session: Session) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(session.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> List[Session]:
        if not self.path.exists():
            return []
        out: List[Session] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(Session.from_dict(json.loads(line)))
                except Exception:  # noqa: BLE001 — skip a corrupt line, don't crash
                    continue
        return out

    def recent(self, n: int = 10) -> List[Session]:
        all_sessions = self.all()
        return all_sessions[-n:][::-1]


def default_path() -> Path:
    env = os.environ.get("TEMPO_STORE")
    if env:
        return Path(env)
    return Path.home() / ".tempo" / "sessions.jsonl"


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
