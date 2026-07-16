from __future__ import annotations

import builtins
import sys
from collections.abc import Callable
from typing import Protocol, cast

from jolt import capture_runtime_enhancements


class _ConsoleReader(Protocol):
    def getwch(self) -> str: ...


def _windows_console_input(prompt: str = "") -> str:
    import msvcrt

    console = cast(_ConsoleReader, msvcrt)
    print(prompt, end="", flush=True)
    while True:
        key = console.getwch()
        if key in ("\r", "\n"):
            print()
            return ""
        if key in ("\x00", "\xe0"):
            console.getwch()


def install_console_input() -> Callable[[str], str] | None:
    if sys.platform != "win32":
        return None

    previous = builtins.input
    builtins.input = _windows_console_input
    return previous


def main() -> int:
    install_console_input()
    return capture_runtime_enhancements.main()


if __name__ == "__main__":
    raise SystemExit(main())
