from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

from photo_flow.progress import ProgressBar

T = TypeVar("T")
R = TypeVar("R")


def default_workers() -> int:
    return min(os.cpu_count() or 1, 8)


def parallel_map(
    items: Sequence[T],
    fn: Callable[[T], R],
    *,
    workers: int,
    desc: str = "",
    label_fn: Callable[[T], str] | None = None,
) -> list[R]:
    """Run ``fn`` on each item using a thread pool with a progress bar.

    Returns results in the **same order** as ``items`` regardless of completion
    order, so callers can zip results back to their inputs.

    Uses threads (not processes) because the work is waiting on external
    subprocesses (sips, magick, exiftool, cjxl) — the GIL is released during
    ``subprocess.run``.
    """

    results: list[R | None] = [None] * len(items)

    if workers <= 1 or len(items) <= 1:
        with ProgressBar(len(items), desc=desc) as bar:
            for index, item in enumerate(items):
                results[index] = fn(item)
                bar.advance(label_fn(item) if label_fn else "")
        return results  # type: ignore[return-value]

    with ProgressBar(len(items), desc=desc) as bar, ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_index = {
            pool.submit(fn, item): (index, item) for index, item in enumerate(items)
        }
        for future in as_completed(future_to_index):
            index, item = future_to_index[future]
            results[index] = future.result()
            bar.advance(label_fn(item) if label_fn else "")

    return results  # type: ignore[return-value]
