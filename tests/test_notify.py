from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from tempo.notify import _escape, notify


def test_escape_handles_quotes() -> None:
    assert _escape('hello "world"') == 'hello \\"world\\"'


def test_escape_handles_backslashes() -> None:
    assert _escape("path\\to\\thing") == "path\\\\to\\\\thing"


def test_notify_never_raises_even_on_bad_input() -> None:
    # Regardless of platform, notify must never raise.
    notify("title with \" quote", "message with \\ slash")


def test_notify_swallows_subprocess_errors() -> None:
    # Even if the underlying subprocess call throws, notify stays silent.
    with patch("tempo.notify.subprocess.run", side_effect=RuntimeError("boom")):
        notify("t", "m")  # must not raise


@pytest.mark.skipif(sys.platform != "darwin", reason="mac path only")
def test_notify_macos_invokes_osascript() -> None:
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

        class _R:
            returncode = 0

        return _R()

    with patch("tempo.notify.subprocess.run", side_effect=fake_run):
        notify("hello", "there")

    assert calls, "expected osascript to be invoked"
    assert calls[0][0] == "osascript"
    # The script arg should contain both the title and message.
    joined = " ".join(calls[0])
    assert "hello" in joined
    assert "there" in joined
