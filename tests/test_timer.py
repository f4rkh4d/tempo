from __future__ import annotations

from tempo.timer import Timer


class FakeClock:
    """Controllable monotonic clock for deterministic tests."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def _timer(duration_sec: int) -> tuple[Timer, FakeClock]:
    clock = FakeClock()
    t = Timer(duration_sec=duration_sec, _now=clock)
    t.start()
    return t, clock


def test_elapsed_progresses_with_clock() -> None:
    t, clock = _timer(60)
    assert t.elapsed == 0
    clock.advance(10)
    assert t.elapsed == 10


def test_remaining_is_target_minus_elapsed() -> None:
    t, clock = _timer(60)
    clock.advance(45)
    assert t.remaining == 15


def test_progress_is_zero_to_one() -> None:
    t, clock = _timer(100)
    clock.advance(25)
    assert abs(t.progress - 0.25) < 1e-9
    clock.advance(200)  # past end
    assert t.progress == 1.0


def test_pause_freezes_elapsed() -> None:
    t, clock = _timer(60)
    clock.advance(10)
    t.pause()
    clock.advance(30)  # paused — shouldn't count
    assert t.elapsed == 10
    t.resume()
    clock.advance(5)
    assert t.elapsed == 15


def test_multiple_pauses_accumulate() -> None:
    t, clock = _timer(60)
    clock.advance(5)
    t.pause()
    clock.advance(10)
    t.resume()
    clock.advance(5)
    t.pause()
    clock.advance(20)
    t.resume()
    clock.advance(5)
    assert t.elapsed == 15  # 5+5+5, with two pauses skipped


def test_toggle_pause() -> None:
    t, clock = _timer(60)
    t.toggle_pause()
    assert t.is_paused
    t.toggle_pause()
    assert not t.is_paused


def test_extend_adds_to_target() -> None:
    t, clock = _timer(60)
    t.extend(30)
    assert t.total_target == 90
    t.extend(15)
    assert t.total_target == 105


def test_is_done_after_full_duration() -> None:
    t, clock = _timer(60)
    assert not t.is_done
    clock.advance(60)
    assert t.is_done


def test_is_done_respects_extensions() -> None:
    t, clock = _timer(60)
    clock.advance(60)
    assert t.is_done
    t.extend(30)
    assert not t.is_done
    clock.advance(30)
    assert t.is_done


def test_actual_sec_rounds_to_int() -> None:
    t, clock = _timer(60)
    clock.advance(29.7)
    assert t.actual_sec() == 30
