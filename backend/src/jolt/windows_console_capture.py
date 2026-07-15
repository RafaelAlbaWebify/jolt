from __future__ import annotations

import builtins
import sys
from collections.abc import Callable

from jolt import supervised_capture


def _windows_console_input(prompt: str = "") -> str:
    import msvcrt

    print(prompt, end="", flush=True)
    while True:
        key = msvcrt.getwch()
        if key in ("\r", "\n"):
            print()
            return ""
        if key in ("\x00", "\xe0"):
            msvcrt.getwch()


def install_console_input() -> Callable[[str], str] | None:
    if sys.platform != "win32":
        return None

    previous = builtins.input
    builtins.input = _windows_console_input
    return previous


def main() -> int:
    install_console_input()
    return supervised_capture.main()


if __name__ == "__main__":
    raise SystemExit(main())
