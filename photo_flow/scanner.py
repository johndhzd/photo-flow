from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from photo_flow.models import RootConfig


TIFF_EXTENSIONS = (".tif", ".tiff")


def files_in(directory: Path, extensions: Sequence[str]) -> tuple[Path, ...]:
    """Return sorted files in ``directory`` whose suffix is in ``extensions``.

    Missing directories yield an empty tuple so callers can decide how to react.
    Matching is case-insensitive, which matters here because cameras emit mixed
    cases such as ``.ARW`` and ``.HIF``.
    """

    if not directory.is_dir():
        return ()
    normalized = {ext.lower() for ext in extensions}
    files = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in normalized
    ]
    return tuple(sorted(files, key=lambda item: item.name.lower()))


def raw_files(config: RootConfig, raw_name: str) -> tuple[Path, ...]:
    return files_in(config.raw_folder(raw_name), config.raw_extensions)


def original_heic_files(config: RootConfig, raw_name: str) -> tuple[Path, ...]:
    return files_in(config.raw_folder(raw_name), config.original_heic_extensions)


def tiff_files(config: RootConfig, session_date: str) -> tuple[Path, ...]:
    return files_in(config.tiff_dir_for(session_date), TIFF_EXTENSIONS)


def processed_files(config: RootConfig, session_date: str) -> tuple[Path, ...]:
    return files_in(config.processed_dir_for(session_date), config.processed_extensions)
