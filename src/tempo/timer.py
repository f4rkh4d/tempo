"""Pure timer logic — pausing, extensions, elapsed math.

Kept separate from the UI so it's easy to test without a terminal.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class Timer:
    """A focus-block timer with pause/resume and duration extension.

    All time accounting is done against a monotonic clock. Construction fixes
    `duration_sec`; live state (paused, extensions, actual elapsed) evolves
    as the caller drives it.
    """

    duration_sec: int
    _now: Callable[[], float] = field(default=time.monotonic)
    _started_at: Optional[float] = None
    _paused: bool = False
    _pause_started: Optional[float] = None
    _paused_total: float = 0.0
    _extensions: List[int] = field(default_factory=list)

    def start(self) -> None:
        self._started_at = self._now()

    @property
    def elapsed(self) -> float:
        """Seconds elapsed since start, excluding paused time."""
        if self._started_at is None:
            return 0.0
        raw = self._now() - self._started_at
        paused_now = (
            (self._now() - self._pause_started)
            if self._paused and self._pause_started is not None
            else 0.0
        )
        return max(0.0, raw - self._paused_total - paused_now)

    @property
    def total_target(self) -> int:
        """Effective target, including any +5-minute extensions."""
        return self.duration_sec + sum(self._extensions)

    @property
    def remaining(self) -> float:
        return max(0.0, self.total_target - self.elapsed)

    @property
    def progress(self) -> float:
        """0.0 .. 1.0 toward completion."""
        if self.total_target <= 0:
            return 1.0
        return min(1.0, self.elapsed / self.total_target)

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_done(self) -> bool:
        return self.remaining <= 0.0 and self._started_at is not None

    def pause(self) -> None:
        if not self._paused:
            self._paused = True
            self._pause_started = self._now()

    def resume(self) -> None:
        if self._paused and self._pause_started is not None:
            self._paused_total += self._now() - self._pause_started
            self._paused = False
            self._pause_started = None

    def toggle_pause(self) -> None:
        if self._paused:
            self.resume()
        else:
            self.pause()

    def extend(self, seconds: int) -> None:
        """Add time to the target."""
        self._extensions.append(int(seconds))

    def actual_sec(self) -> int:
        """Whole-second elapsed, for storing in the session record."""
        return int(round(self.elapsed))
