"""tempo-bar — macOS menu bar companion.

Small rumps-based menubar app. Click the icon → pick a tag + duration,
session starts, a live countdown shows in the menubar title. Pause /
+5 min / abort via menu items. On completion: desktop notification +
session appended to the same `~/.tempo/sessions.jsonl` store.

macOS only. Install with: `pip install tempo[menubar]`.
Run with: `tempo-bar`.
"""

from __future__ import annotations

import sys
from typing import Optional

from .notify import notify
from .store import Session, Store, iso_now
from .timer import Timer


def _require_rumps():
    try:
        import rumps  # type: ignore
    except ImportError as exc:
        sys.stderr.write(
            "tempo-bar needs the `rumps` package. install it with:\n"
            "    pip install tempo[menubar]\n"
        )
        raise SystemExit(2) from exc
    return rumps


def _fmt_countdown(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    m, s = divmod(total, 60)
    return f"{m:02d}:{s:02d}"


class TempoBar:
    """The menubar state machine."""

    def __init__(self) -> None:
        self.rumps = _require_rumps()
        # Use plain text for the menubar title — emoji rendering is
        # inconsistent across macOS versions and hard to spot when idle.
        self.app = self.rumps.App("tempo", title="● tempo", quit_button=None)
        self.timer: Optional[Timer] = None
        self.tag: str = ""
        self.started_at_iso: str = ""

        self.item_start = self.rumps.MenuItem("start 25min", callback=self._on_start)
        self.menu_start_sub = self.rumps.MenuItem("start…")
        for minutes in (15, 25, 45, 60, 90):
            self.menu_start_sub.add(
                self.rumps.MenuItem(
                    f"{minutes} min",
                    callback=lambda sender, m=minutes: self._start_session(m, ""),
                )
            )

        self.menu_start_tag = self.rumps.MenuItem("start with tag…")
        for tag in ("uni", "code", "reading", "writing"):
            self.menu_start_tag.add(
                self.rumps.MenuItem(
                    tag,
                    callback=lambda sender, t=tag: self._prompt_duration_then_start(t),
                )
            )
        self.menu_start_tag.add(self.rumps.separator)
        self.menu_start_tag.add(
            self.rumps.MenuItem("custom tag…", callback=self._on_custom_tag)
        )

        self.item_pause = self.rumps.MenuItem("pause", callback=self._on_pause)
        self.item_extend = self.rumps.MenuItem("add 5 min", callback=self._on_extend)
        self.item_abort = self.rumps.MenuItem("abort session", callback=self._on_abort)
        self.item_stats = self.rumps.MenuItem("show stats", callback=self._on_stats)
        self.item_quit = self.rumps.MenuItem("quit", callback=self._on_quit)

        self.app.menu = [
            self.item_start,
            self.menu_start_sub,
            self.menu_start_tag,
            None,  # separator
            self.item_pause,
            self.item_extend,
            self.item_abort,
            None,
            self.item_stats,
            None,
            self.item_quit,
        ]

        self._update_menu_visibility()

        # Tick once per second to refresh the menubar title.
        self.ticker = self.rumps.Timer(self._tick, 1)

    def run(self) -> None:
        # fire a startup notification so the user knows it's alive, even if
        # the menubar is crowded and the icon is hard to spot.
        notify("tempo-bar started", "look for 🍅 tempo in your menu bar (top right).")
        self.app.run()

    # ---- callbacks ----

    def _on_start(self, _sender) -> None:
        self._start_session(25, "")

    def _on_custom_tag(self, _sender) -> None:
        resp = self.rumps.Window("tag?", "start focus session", dimensions=(200, 20)).run()
        if resp.clicked:
            self._prompt_duration_then_start(resp.text.strip())

    def _prompt_duration_then_start(self, tag: str) -> None:
        resp = self.rumps.Window(
            "duration (minutes)?",
            f"start: {tag or 'focus'}",
            default_text="25",
            dimensions=(80, 20),
        ).run()
        if not resp.clicked:
            return
        try:
            minutes = int(resp.text.strip() or "25")
        except ValueError:
            return
        if minutes <= 0:
            return
        self._start_session(minutes, tag)

    def _on_pause(self, _sender) -> None:
        if self.timer is None:
            return
        self.timer.toggle_pause()
        self.item_pause.title = "resume" if self.timer.is_paused else "pause"

    def _on_extend(self, _sender) -> None:
        if self.timer is None:
            return
        self.timer.extend(5 * 60)

    def _on_abort(self, _sender) -> None:
        if self.timer is None:
            return
        self._finish(status="aborted")

    def _on_stats(self, _sender) -> None:
        from .stats import format_duration, summary
        summ = summary(Store().all(), window="week")
        if summ.session_count == 0:
            self.rumps.notification("tempo", "last 7d", "no sessions yet.")
            return
        top = list(summ.by_tag_sec.items())[:3]
        body_parts = [f"{summ.format_total()} across {summ.session_count} sessions."]
        for tag, sec in top:
            body_parts.append(f"{tag}: {format_duration(sec)}")
        self.rumps.notification("tempo — last 7d", "", "\n".join(body_parts))

    def _on_quit(self, _sender) -> None:
        if self.timer is not None and not self.timer.is_done:
            self._finish(status="aborted")
        self.rumps.quit_application()

    # ---- internal ----

    def _start_session(self, minutes: int, tag: str) -> None:
        if self.timer is not None and not self.timer.is_done:
            self.rumps.notification("tempo", "already running", "finish or abort first.")
            return
        self.tag = tag
        self.started_at_iso = iso_now()
        self.timer = Timer(duration_sec=minutes * 60)
        self.timer.start()
        self.item_pause.title = "pause"
        self._update_menu_visibility()
        self.ticker.start()

    def _finish(self, status: str) -> None:
        if self.timer is None:
            return
        actual = self.timer.actual_sec()
        sess = Session(
            started_at=self.started_at_iso,
            ended_at=iso_now(),
            duration_sec=self.timer.duration_sec,
            actual_sec=actual,
            tag=self.tag,
            note="",
            status=status,
        )
        Store().append(sess)

        from .stats import format_duration
        tag_suffix = f" · {self.tag}" if self.tag else ""
        if status == "done":
            notify("tempo — focus done", f"{format_duration(actual)}{tag_suffix}. good work.")
        else:
            notify("tempo — session aborted", f"{format_duration(actual)}{tag_suffix} logged.")

        self.timer = None
        self.tag = ""
        self.started_at_iso = ""
        self.ticker.stop()
        self.app.title = "● tempo"
        self._update_menu_visibility()

    def _tick(self, _sender) -> None:
        if self.timer is None:
            return
        if self.timer.is_done:
            self._finish(status="done")
            return
        tag_bit = f" {self.tag}" if self.tag else ""
        paused_bit = " (paused)" if self.timer.is_paused else ""
        self.app.title = f"●{tag_bit} {_fmt_countdown(self.timer.remaining)}{paused_bit}"

    def _update_menu_visibility(self) -> None:
        active = self.timer is not None and not self.timer.is_done
        self.item_pause.set_callback(self._on_pause if active else None)
        self.item_extend.set_callback(self._on_extend if active else None)
        self.item_abort.set_callback(self._on_abort if active else None)


def main() -> None:
    if sys.platform != "darwin":
        sys.stderr.write("tempo-bar is macOS-only right now. use `tempo start` instead.\n")
        raise SystemExit(2)
    TempoBar().run()


if __name__ == "__main__":
    main()
