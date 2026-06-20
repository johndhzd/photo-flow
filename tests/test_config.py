from pathlib import Path

import pytest
import yaml

from photo_flow.config import ConfigError, load_config
from photo_flow.models import OutputFormat


def write_config(path: Path, **overrides):
    data = {
        "root_dir": str(path.parent / "PhotoEdit"),
        "default_format": "heic",
        "default_quality": 90,
        "overwrite_existing": False,
        "raw_extensions": [".arw", "CR3", ".dng"],
    }
    data.update(overrides)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_load_config_normalizes_values(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)

    config = load_config(config_path)

    root = tmp_path / "PhotoEdit"
    assert config.root_dir == root
    assert config.raw_photos_dir == root / "RawPhotos"
    assert config.processed_photos_dir == root / "ProcessedPhotos"
    assert config.tiff_dir == root / "TIFF"
    assert config.backups_dir == root / "Backups"
    assert config.log_dir == root / "Backups" / "logs"
    assert config.default_format == OutputFormat.HEIC
    assert config.default_quality == 90
    assert config.overwrite_existing is False
    assert config.raw_extensions == (".arw", ".cr3", ".dng")
    assert config.original_heic_extensions == (".hif", ".heic", ".heif")
    assert config.processed_extensions == (".heic", ".jpg", ".jpeg", ".png", ".jxl")
    assert config.session_map == {}


def test_load_config_applies_defaults(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        default_format=None,
        default_quality=None,
        overwrite_existing=None,
        raw_extensions=None,
    )

    config = load_config(config_path)

    assert config.default_format == OutputFormat.HEIC
    assert config.default_quality == 90
    assert config.overwrite_existing is False
    assert config.raw_extensions == (".arw", ".cr3", ".nef", ".raf", ".rw2", ".dng")


def test_load_config_supports_custom_subdirs_and_session_map(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        raw_photos_subdir="Raw",
        backups_subdir="Out",
        log_dir=str(tmp_path / "mylogs"),
        session_map={"10460308": "2026_03_08"},
    )

    config = load_config(config_path)

    assert config.raw_photos_dir == tmp_path / "PhotoEdit" / "Raw"
    assert config.backups_dir == tmp_path / "PhotoEdit" / "Out"
    assert config.log_dir == tmp_path / "mylogs"
    assert config.session_map == {"10460308": "2026_03_08"}


def test_load_config_rejects_missing_root_dir(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    del data["root_dir"]
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ConfigError, match="Missing required config value: root_dir"):
        load_config(config_path)


def test_load_config_rejects_bad_quality(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path, default_quality=101)

    with pytest.raises(ConfigError, match="default_quality must be between 1 and 100"):
        load_config(config_path)
