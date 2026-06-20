from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class OutputFormat(StrEnum):
    HEIC = "heic"
    JPG = "jpg"
    PNG = "png"
    JXL = "jxl"

    @classmethod
    def parse(cls, value: str) -> "OutputFormat":
        normalized = value.strip().lower()
        if normalized == "jpeg":
            normalized = "jpg"
        try:
            return cls(normalized)
        except ValueError as exc:
            supported = ", ".join(item.value for item in cls)
            raise ValueError(f"Unsupported output format '{value}'. Supported: {supported}") from exc


def format_extension(output_format: OutputFormat) -> str:
    return {
        OutputFormat.HEIC: ".heic",
        OutputFormat.JPG: ".jpg",
        OutputFormat.PNG: ".png",
        OutputFormat.JXL: ".jxl",
    }[output_format]


@dataclass(frozen=True)
class RootConfig:
    """Root-based layout for /Volumes/FastData/PhotoEdit and similar trees.

    A single config points at one root that contains many photo sessions. Each
    session is identified by a ``YYYY_MM_DD`` folder name in the processed/tiff
    trees, while the original capture folder under ``RawPhotos`` uses a separate
    naming convention that must be matched back to a date.
    """

    root_dir: Path
    raw_photos_subdir: str
    processed_photos_subdir: str
    tiff_subdir: str
    backups_subdir: str
    log_dir: Path
    default_format: OutputFormat
    default_quality: int
    overwrite_existing: bool
    raw_extensions: tuple[str, ...]
    original_heic_extensions: tuple[str, ...]
    processed_extensions: tuple[str, ...]
    session_map: dict[str, str] = field(default_factory=dict)

    @property
    def raw_photos_dir(self) -> Path:
        return self.root_dir / self.raw_photos_subdir

    @property
    def processed_photos_dir(self) -> Path:
        return self.root_dir / self.processed_photos_subdir

    @property
    def tiff_dir(self) -> Path:
        return self.root_dir / self.tiff_subdir

    @property
    def backups_dir(self) -> Path:
        return self.root_dir / self.backups_subdir

    def raw_folder(self, raw_name: str) -> Path:
        return self.raw_photos_dir / raw_name

    def processed_dir_for(self, session_date: str) -> Path:
        return self.processed_photos_dir / session_date

    def tiff_dir_for(self, session_date: str) -> Path:
        return self.tiff_dir / session_date

    def backup_work_dir(self, session_date: str) -> Path:
        return self.backups_dir / session_date


@dataclass(frozen=True)
class ConversionPlan:
    source_tiff: Path
    output_file: Path
    output_format: OutputFormat
    quality: int


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0
