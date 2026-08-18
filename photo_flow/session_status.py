from __future__ import annotations

from dataclasses import dataclass

from photo_flow.models import RootConfig
from photo_flow.scanner import (
    original_heic_files,
    processed_files,
    raw_files,
    tiff_files,
)
from photo_flow.sessions import suggest_raw_for_date

# Category zip names produced inside Backups/<date>. Kept here (not imported from
# cli) so the status panel has no dependency on the CLI command layer.
HEIC_ZIP = "original_heic.zip"
RAW_ZIP = "original_raw.zip"
EDITED_ZIP = "edited.zip"


@dataclass(frozen=True)
class SessionStatus:
    """Read-only snapshot of a session for the TUI detail panel.

    All fields are plain data derived from the filesystem so this can be built
    and asserted without a live terminal.
    """

    session_date: str
    tiff_count: int
    processed_count: int
    raw_name: str | None
    raw_count: int
    original_heic_count: int
    heic_zip_exists: bool
    raw_zip_exists: bool
    edited_zip_exists: bool


def match_raw_folder(config: RootConfig, session_date: str) -> str | None:
    """Best-effort, non-interactive RawPhotos match for a session date.

    Mirrors the resolution order of ``resolve_raw_folder`` (session_map first,
    then the trailing-MMDD suggestion) but never prompts and returns ``None``
    when nothing matches or the mapped folder is missing.
    """

    mapped = next(
        (name for name, value in config.session_map.items() if value == session_date),
        None,
    )
    if mapped and config.raw_folder(mapped).is_dir():
        return mapped

    suggestion = suggest_raw_for_date(config, session_date)
    if suggestion and config.raw_folder(suggestion).is_dir():
        return suggestion
    return None


def build_session_status(config: RootConfig, session_date: str) -> SessionStatus:
    raw_name = match_raw_folder(config, session_date)
    raw_count = len(raw_files(config, raw_name)) if raw_name else 0
    original_heic_count = len(original_heic_files(config, raw_name)) if raw_name else 0

    work_dir = config.backup_work_dir(session_date)
    return SessionStatus(
        session_date=session_date,
        tiff_count=len(tiff_files(config, session_date)),
        processed_count=len(processed_files(config, session_date)),
        raw_name=raw_name,
        raw_count=raw_count,
        original_heic_count=original_heic_count,
        heic_zip_exists=(work_dir / HEIC_ZIP).exists(),
        raw_zip_exists=(work_dir / RAW_ZIP).exists(),
        edited_zip_exists=(work_dir / EDITED_ZIP).exists(),
    )
