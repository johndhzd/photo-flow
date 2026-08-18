from __future__ import annotations

import contextvars
import os
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import TracebackType

# A progress sink receives (current, total, desc) on every advance. When a sink
# is installed (e.g. by the TUI) ProgressBar routes updates to it instead of
# drawing an ANSI bar on stderr, so progress never corrupts the terminal UI.
ProgressSink = Callable[[int, int, str], None]

_progress_sink: contextvars.ContextVar[ProgressSink | None] = contextvars.ContextVar(
    "photo_flow_progress_sink", default=None
)


@contextmanager
def progress_sink(sink: ProgressSink | None) -> Iterator[None]:
    """Install ``sink`` as the active progress reporter for the current context.

    Restores the previous sink on exit so nested/concurrent jobs stay isolated.
    """

    token = _progress_sink.set(sink)
    try:
        yield
    finally:
        _progress_sink.reset(token)


class ProgressBar:
    """Minimal terminal progress bar that writes to stderr.

    Writes to stderr so it never pollutes stdout piping or test capsys
    assertions. Becomes a no-op when stderr is not connected to a TTY
    (CI, pytest, pipes). Thread-safe: multiple workers may call
    ``advance`` concurrently.

    When a progress sink is installed via :func:`progress_sink`, updates are
    forwarded to the sink and nothing is written to stderr, so the bar can be
    embedded in a richer UI such as the TUI.
    """

    def __init__(self, total: int, *, desc: str = "", bar_width: int = 28) -> None:
        self._total = max(total, 1)
        self._current = 0
        self._desc = desc
        self._bar_width = bar_width
        self._tty = sys.stderr.isatty()
        self._lock = threading.Lock()
        self._sink = _progress_sink.get()

    def advance(self, label: str = "") -> None:
        with self._lock:
            self._current += 1
            if self._sink is not None:
                self._sink(self._current, self._total, self._desc)
                return
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
        if self._sink is None and self._tty:
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
