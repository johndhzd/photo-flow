from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from photo_flow.models import AppConfig, OutputFormat


DEFAULT_RAW_EXTENSIONS = (".arw", ".cr3", ".nef", ".raf", ".rw2", ".dng")


class ConfigError(ValueError):
    pass


def load_config(path: Path) -> AppConfig:
    try:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML config: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise ConfigError("Config file must contain a YAML mapping")

    data: dict[str, Any] = raw_data
    required = (
        "raw_dir",
        "original_heic_dir",
        "tiff_dir",
        "converted_output_dir",
        "log_dir",
        "backup_destinations",
    )
    for key in required:
        if not data.get(key):
            raise ConfigError(f"Missing required config value: {key}")

    default_format = data.get("default_format") or "heic"
    try:
        output_format = OutputFormat.parse(str(default_format))
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    quality = _parse_quality(data.get("default_quality"))
    overwrite_existing = bool(data.get("overwrite_existing") or False)
    raw_extensions = _normalize_extensions(data.get("raw_extensions") or DEFAULT_RAW_EXTENSIONS)
    destinations = data["backup_destinations"]
    if not isinstance(destinations, list) or not destinations:
        raise ConfigError("backup_destinations must be a non-empty list")

    return AppConfig(
        raw_dir=Path(data["raw_dir"]).expanduser(),
        original_heic_dir=Path(data["original_heic_dir"]).expanduser(),
        tiff_dir=Path(data["tiff_dir"]).expanduser(),
        converted_output_dir=Path(data["converted_output_dir"]).expanduser(),
        log_dir=Path(data["log_dir"]).expanduser(),
        default_format=output_format,
        default_quality=quality,
        overwrite_existing=overwrite_existing,
        raw_extensions=raw_extensions,
        backup_destinations=tuple(Path(item).expanduser() for item in destinations),
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


def _normalize_extensions(values: object) -> tuple[str, ...]:
    if not isinstance(values, list | tuple):
        raise ConfigError("raw_extensions must be a list")
    normalized: list[str] = []
    for value in values:
        ext = str(value).strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.append(ext)
    if not normalized:
        raise ConfigError("raw_extensions must include at least one extension")
    return tuple(dict.fromkeys(normalized))
