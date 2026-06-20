from pathlib import Path

from photo_flow.models import OutputFormat, RootConfig


def build_root_config(root: Path, **overrides) -> RootConfig:
    defaults = dict(
        root_dir=root,
        raw_photos_subdir="RawPhotos",
        processed_photos_subdir="ProcessedPhotos",
        tiff_subdir="TIFF",
        backups_subdir="Backups",
        log_dir=root / "Backups" / "logs",
        default_format=OutputFormat.HEIC,
        default_quality=90,
        overwrite_existing=False,
        raw_extensions=(".arw", ".cr3", ".dng"),
        original_heic_extensions=(".hif", ".heic", ".heif"),
        processed_extensions=(".heic", ".jpg", ".jpeg", ".png", ".jxl"),
        session_map={},
    )
    defaults.update(overrides)
    return RootConfig(**defaults)


def touch(path: Path, content: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
