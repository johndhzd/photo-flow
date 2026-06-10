from __future__ import annotations

from dataclasses import dataclass
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
class AppConfig:
    raw_dir: Path
    original_heic_dir: Path
    tiff_dir: Path
    converted_output_dir: Path
    log_dir: Path
    default_format: OutputFormat
    default_quality: int
    overwrite_existing: bool
    raw_extensions: tuple[str, ...]
    backup_destinations: tuple[Path, ...]


@dataclass(frozen=True)
class SessionInventory:
    raw_files: tuple[Path, ...]
    original_heic_files: tuple[Path, ...]
    tiff_files: tuple[Path, ...]


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
