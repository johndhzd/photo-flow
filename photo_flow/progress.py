from __future__ import annotations

import os
import sys
import threading
from types import TracebackType


class ProgressBar:
    """Minimal terminal progress bar that writes to stderr.

    Writes to stderr so it never pollutes stdout piping or test capsys
    assertions. Becomes a no-op when stderr is not connected to a TTY
    (CI, pytest, pipes). Thread-safe: multiple workers may call
    ``advance`` concurrently.
    """

    def __init__(self, total: int, *, desc: str = "", bar_width: int = 28) -> None:
        self._total = max(total, 1)
        self._current = 0
        self._desc = desc
        self._bar_width = bar_width
        self._tty = sys.stderr.isatty()
        self._lock = threading.Lock()

    def advance(self, label: str = "") -> None:
        with self._lock:
            self._current += 1
            if not self._tty:
                return
            filled = int(self._bar_width * self._current / self._total)
            bar = "=" * filled + " " * (self._bar_width - filled)
            pct = int(100 * self._current / self._total)
            counter = f"({self._current}/{self._total})"
            prefix = f"{self._desc} " if self._desc else ""
            line = f"\r{prefix}[{bar}] {pct:3d}% {counter}  {label}"
            try:
                cols = os.get_terminal_size().columns
            except OSError:
                cols = 80
            sys.stderr.write(line[:cols])
            sys.stderr.flush()

    def finish(self) -> None:
        if self._tty:
            sys.stderr.write("\n")
            sys.stderr.flush()

    def __enter__(self) -> "ProgressBar":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.finish()
