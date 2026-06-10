import yaml

from photo_flow.cli import main


def test_estimate_command_prints_estimate(tmp_path, capsys):
    raw = tmp_path / "raw"
    heic = tmp_path / "heic"
    tiff = tmp_path / "tiff"
    converted = tmp_path / "converted"
    logs = tmp_path / "logs"
    backup = tmp_path / "backup"
    for directory in (raw, heic, tiff, converted, logs, backup):
        directory.mkdir()
    (tiff / "DSC0001.tif").write_bytes(b"x" * 100)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "raw_dir": str(raw),
                "original_heic_dir": str(heic),
                "tiff_dir": str(tiff),
                "converted_output_dir": str(converted),
                "log_dir": str(logs),
                "backup_destinations": [str(backup)],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["estimate", "--config", str(config_path), "--dry-sample-size", "40"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Estimated converted output size" in captured.out
    assert "heic" in captured.out
