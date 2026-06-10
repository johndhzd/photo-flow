from pathlib import Path

import pytest

from photo_flow.models import AppConfig, OutputFormat
from photo_flow.scanner import ScanError, scan_session


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        raw_dir=tmp_path / "raw",
        original_heic_dir=tmp_path / "original_heic",
        tiff_dir=tmp_path / "tiff",
        converted_output_dir=tmp_path / "converted",
        log_dir=tmp_path / "logs",
        default_format=OutputFormat.HEIC,
        default_quality=90,
        overwrite_existing=False,
        raw_extensions=(".arw", ".cr3", ".dng"),
        backup_destinations=(tmp_path / "backup",),
    )


def touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def test_scan_session_collects_supported_files_sorted(tmp_path):
    config = make_config(tmp_path)
    touch(config.raw_dir / "DSC0002.ARW")
    touch(config.raw_dir / "DSC0001.cr3")
    touch(config.raw_dir / "ignore.txt")
    touch(config.original_heic_dir / "DSC0001.HEIC")
    touch(config.tiff_dir / "DSC0001.tif")
    touch(config.tiff_dir / "DSC0002.TIFF")

    inventory = scan_session(config)

    assert [p.name for p in inventory.raw_files] == ["DSC0001.cr3", "DSC0002.ARW"]
    assert [p.name for p in inventory.original_heic_files] == ["DSC0001.HEIC"]
    assert [p.name for p in inventory.tiff_files] == ["DSC0001.tif", "DSC0002.TIFF"]
    assert config.converted_output_dir.is_dir()
    assert config.log_dir.is_dir()


def test_scan_session_requires_source_directories(tmp_path):
    config = make_config(tmp_path)
    config.raw_dir.mkdir(parents=True)

    with pytest.raises(ScanError, match="Required directory does not exist"):
        scan_session(config)
