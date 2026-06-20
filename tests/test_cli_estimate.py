import yaml

from photo_flow.cli import main


def write_config(tmp_path):
    root = tmp_path / "PhotoEdit"
    (root / "TIFF" / "2026_03_08").mkdir(parents=True)
    (root / "TIFF" / "2026_03_08" / "DSC0001.tif").write_bytes(b"x" * 100)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"root_dir": str(root)}), encoding="utf-8")
    return config_path


def test_estimate_command_prints_estimate(tmp_path, capsys):
    config_path = write_config(tmp_path)

    exit_code = main(
        [
            "estimate",
            "--config",
            str(config_path),
            "--date",
            "2026_03_08",
            "--dry-sample-size",
            "40",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Estimated converted output size" in captured.out
    assert "Session: 2026_03_08" in captured.out
    assert "heic" in captured.out
