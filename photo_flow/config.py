from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from photo_flow.models import OutputFormat, RootConfig


DEFAULT_RAW_EXTENSIONS = (".arw", ".cr3", ".nef", ".raf", ".rw2", ".dng")
DEFAULT_ORIGINAL_HEIC_EXTENSIONS = (".hif", ".heic", ".heif")
DEFAULT_PROCESSED_EXTENSIONS = (".heic", ".jpg", ".jpeg", ".png", ".jxl")

DEFAULT_RAW_PHOTOS_SUBDIR = "RawPhotos"
DEFAULT_PROCESSED_PHOTOS_SUBDIR = "ProcessedPhotos"
DEFAULT_TIFF_SUBDIR = "TIFF"
DEFAULT_BACKUPS_SUBDIR = "Backups"


class ConfigError(ValueError):
    pass


def load_config(path: Path) -> RootConfig:
    try:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML config: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise ConfigError("Config file must contain a YAML mapping")

    data: dict[str, Any] = raw_data
    if not data.get("root_dir"):
        raise ConfigError("Missing required config value: root_dir")

    root_dir = Path(data["root_dir"]).expanduser()
    raw_photos_subdir = str(data.get("raw_photos_subdir") or DEFAULT_RAW_PHOTOS_SUBDIR)
    processed_photos_subdir = str(data.get("processed_photos_subdir") or DEFAULT_PROCESSED_PHOTOS_SUBDIR)
    tiff_subdir = str(data.get("tiff_subdir") or DEFAULT_TIFF_SUBDIR)
    backups_subdir = str(data.get("backups_subdir") or DEFAULT_BACKUPS_SUBDIR)

    log_dir_value = data.get("log_dir")
    if log_dir_value:
        log_dir = Path(log_dir_value).expanduser()
    else:
        log_dir = root_dir / backups_subdir / "logs"

    default_format = data.get("default_format") or "heic"
    try:
        output_format = OutputFormat.parse(str(default_format))
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    quality = _parse_quality(data.get("default_quality"))
    overwrite_existing = bool(data.get("overwrite_existing") or False)
    raw_extensions = _normalize_extensions(
        data.get("raw_extensions") or DEFAULT_RAW_EXTENSIONS, "raw_extensions"
    )
    original_heic_extensions = _normalize_extensions(
        data.get("original_heic_extensions") or DEFAULT_ORIGINAL_HEIC_EXTENSIONS,
        "original_heic_extensions",
    )
    processed_extensions = _normalize_extensions(
        data.get("processed_extensions") or DEFAULT_PROCESSED_EXTENSIONS,
        "processed_extensions",
    )
    session_map = _normalize_session_map(data.get("session_map"))

    return RootConfig(
        root_dir=root_dir,
        raw_photos_subdir=raw_photos_subdir,
        processed_photos_subdir=processed_photos_subdir,
        tiff_subdir=tiff_subdir,
        backups_subdir=backups_subdir,
        log_dir=log_dir,
        default_format=output_format,
        default_quality=quality,
        overwrite_existing=overwrite_existing,
        raw_extensions=raw_extensions,
        original_heic_extensions=original_heic_extensions,
        processed_extensions=processed_extensions,
        session_map=session_map,
    )


def _parse_quality(value: object) -> int:
    if value is None:
        value = 90
    try:
        quality = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError("default_quality must be an integer between 1 and 100") from exc
    if not 1 <= quality <= 100:
        raise ConfigError("default_quality must be between 1 and 100")
    return quality


def _normalize_extensions(values: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, list | tuple):
        raise ConfigError(f"{field_name} must be a list")
    normalized: list[str] = []
    for value in values:
        ext = str(value).strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.append(ext)
    if not normalized:
        raise ConfigError(f"{field_name} must include at least one extension")
    return tuple(dict.fromkeys(normalized))


def _normalize_session_map(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("session_map must be a mapping of raw_folder_name to YYYY_MM_DD")
    return {str(key): str(item) for key, item in value.items()}
