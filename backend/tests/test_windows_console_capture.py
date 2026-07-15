from __future__ import annotations

import builtins
import sys
from types import SimpleNamespace

from jolt.windows_console_capture import install_console_input


def test_windows_console_confirmation_bypasses_inherited_stdin(monkeypatch, capsys) -> None:
    keys = iter(["x", "\x00", "ignored-special-key", "\r"])
    fake_msvcrt = SimpleNamespace(getwch=lambda: next(keys))
    original_input = builtins.input

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)

    previous = install_console_input()
    try:
        assert previous is original_input
        assert builtins.input("Press Enter to start the bounded capture: ") == ""
    finally:
        builtins.input = original_input

    assert capsys.readouterr().out == "Press Enter to start the bounded capture: \n"


def test_non_windows_keeps_standard_input(monkeypatch) -> None:
    original_input = builtins.input
    monkeypatch.setattr(sys, "platform", "linux")

    assert install_console_input() is None
    assert builtins.input is original_input
