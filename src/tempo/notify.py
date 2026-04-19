"""Best-effort desktop notifications.

Tries platform-native paths (`osascript` on macOS, `notify-send` on Linux,
`PowerShell BurntToast` hint on Windows). Silent on platforms where nothing
works — never crashes, never blocks.
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def notify(title: str, message: str) -> None:
    """Show a desktop notification. Never raises."""
    try:
        if sys.platform == "darwin":
            _notify_macos(title, message)
        elif sys.platform.startswith("linux"):
            _notify_linux(title, message)
        else:
            # Windows / other — give up silently. Could extend later.
            pass
    except Exception:  # noqa: BLE001 — notifications must never crash the app
        pass


def _notify_macos(title: str, message: str) -> None:
    # osascript is shipped with every macOS install.
    script = (
        'display notification "{msg}" with title "{title}"'
    ).format(msg=_escape(message), title=_escape(title))
    subprocess.run(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=3,
    )


def _notify_linux(title: str, message: str) -> None:
    # notify-send from libnotify. Not always installed; skip if missing.
    if shutil.which("notify-send") is None:
        return
    subprocess.run(
        ["notify-send", "--app-name=tempo", title, message],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=3,
    )


def _escape(s: str) -> str:
    """Escape double quotes and backslashes for embedding in AppleScript."""
    return s.replace("\\", "\\\\").replace('"', '\\"')
