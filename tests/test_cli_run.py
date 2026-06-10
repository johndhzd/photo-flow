import yaml

from photo_flow.cli import main


def make_config(tmp_path):
    raw = tmp_path / "raw"
    heic = tmp_path / "heic"
    tiff = tmp_path / "tiff"
    converted = tmp_path / "converted"
    logs = tmp_path / "logs"
    backup = tmp_path / "backup"
    for directory in (raw, heic, tiff, converted, logs, backup):
        directory.mkdir()
    (raw / "DSC0001.ARW").write_bytes(b"raw")
    (heic / "DSC0001.heic").write_bytes(b"original")
    (tiff / "DSC0001.tif").write_bytes(b"tiff")
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
    return config_path, converted, logs, backup


def test_run_command_dry_run_completes_without_external_tools(tmp_path, capsys):
    config_path, converted, logs, backup = make_config(tmp_path)

    exit_code = main([
        "run",
        "--config",
        str(config_path),
        "--tags",
        "test",
        "--yes",
        "--dry-run",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Dry run completed" in captured.out
    assert "DSC0001.heic" in captured.out
