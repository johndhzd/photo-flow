from __future__ import annotations

from pathlib import Path

from photo_flow.models import AppConfig, SessionInventory


TIFF_EXTENSIONS = (".tif", ".tiff")
HEIC_EXTENSIONS = (".heic", ".heif")


class ScanError(RuntimeError):
    pass


def scan_session(config: AppConfig) -> SessionInventory:
    for directory in (config.raw_dir, config.original_heic_dir, config.tiff_dir):
        if not directory.exists() or not directory.is_dir():
            raise ScanError(f"Required directory does not exist: {directory}")

    config.converted_output_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)

    return SessionInventory(
        raw_files=_files_with_extensions(config.raw_dir, config.raw_extensions),
        original_heic_files=_files_with_extensions(config.original_heic_dir, HEIC_EXTENSIONS),
        tiff_files=_files_with_extensions(config.tiff_dir, TIFF_EXTENSIONS),
    )


def _files_with_extensions(directory: Path, extensions: tuple[str, ...]) -> tuple[Path, ...]:
    normalized = {ext.lower() for ext in extensions}
    files = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in normalized
    ]
    return tuple(sorted(files, key=lambda item: item.name.lower()))
