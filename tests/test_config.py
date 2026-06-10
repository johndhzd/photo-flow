from pathlib import Path

import pytest
import yaml

from photo_flow.config import ConfigError, load_config
from photo_flow.models import OutputFormat


def write_config(path: Path, **overrides):
    data = {
        "raw_dir": str(path.parent / "raw"),
        "original_heic_dir": str(path.parent / "original_heic"),
        "tiff_dir": str(path.parent / "tiff"),
        "converted_output_dir": str(path.parent / "converted"),
        "log_dir": str(path.parent / "logs"),
        "default_format": "heic",
        "default_quality": 90,
        "overwrite_existing": False,
        "raw_extensions": [".arw", "CR3", ".dng"],
        "backup_destinations": [str(path.parent / "backup1"), str(path.parent / "backup2")],
    }
    data.update(overrides)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_load_config_normalizes_values(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)

    config = load_config(config_path)

    assert config.raw_dir == tmp_path / "raw"
    assert config.default_format == OutputFormat.HEIC
    assert config.default_quality == 90
    assert config.overwrite_existing is False
    assert config.raw_extensions == (".arw", ".cr3", ".dng")
    assert config.backup_destinations == (tmp_path / "backup1", tmp_path / "backup2")


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


def test_load_config_rejects_missing_required_field(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    del data["raw_dir"]
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ConfigError, match="Missing required config value: raw_dir"):
        load_config(config_path)


def test_load_config_rejects_bad_quality(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path, default_quality=101)

    with pytest.raises(ConfigError, match="default_quality must be between 1 and 100"):
        load_config(config_path)
