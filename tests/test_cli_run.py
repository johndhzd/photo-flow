import zipfile

import yaml

from photo_flow.cli import main


def write_config(tmp_path, *, with_edited=True):
    root = tmp_path / "PhotoEdit"
    raw = root / "RawPhotos" / "10460308"
    raw.mkdir(parents=True)
    (raw / "DSC0001.ARW").write_bytes(b"raw")
    (raw / "DSC0001.HIF").write_bytes(b"hif")
    if with_edited:
        processed = root / "ProcessedPhotos" / "2026_03_08"
        processed.mkdir(parents=True)
        (processed / "DSC0001.heic").write_bytes(b"edited")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"root_dir": str(root)}), encoding="utf-8")
    return config_path, root


def test_backup_heic_creates_zip(tmp_path, capsys):
    config_path, root = write_config(tmp_path)

    exit_code = main(
        [
            "backup-heic",
            "--config",
            str(config_path),
            "--date",
            "2026_03_08",
            "--raw",
            "10460308",
            "--yes",
        ]
    )

    assert exit_code == 0
    heic_zip = root / "Backups" / "2026_03_08" / "original_heic.zip"
    assert heic_zip.exists()
    with zipfile.ZipFile(heic_zip) as archive:
        assert archive.namelist() == ["DSC0001.HIF"]


def test_run_full_pipeline_without_external_tools(tmp_path, capsys):
    config_path, root = write_config(tmp_path)

    exit_code = main(
        [
            "run",
            "--config",
            str(config_path),
            "--date",
            "2026_03_08",
            "--tags",
            "japan,street",
            "--keep-intermediate",
            "--yes",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    final = root / "Backups" / "2026_03_08_japan_street.zip"
    assert final.exists()
    assert "Bundle created" in captured.out

    work = root / "Backups" / "2026_03_08"
    assert (work / "original_heic.zip").exists()
    assert (work / "original_raw.zip").exists()
    assert (work / "edited.zip").exists()

    with zipfile.ZipFile(final) as archive:
        assert sorted(archive.namelist()) == [
            "edited.zip",
            "original_heic.zip",
            "original_raw.zip",
        ]


def test_run_matches_raw_folder_via_suggestion(tmp_path):
    config_path, root = write_config(tmp_path)

    exit_code = main(
        [
            "run",
            "--config",
            str(config_path),
            "--date",
            "2026_03_08",
            "--keep-intermediate",
            "--yes",
        ]
    )

    assert exit_code == 0
    assert (root / "Backups" / "2026_03_08.zip").exists()


def test_bundle_requires_existing_category_zips(tmp_path, capsys):
    config_path, root = write_config(tmp_path)

    exit_code = main(
        [
            "bundle",
            "--config",
            str(config_path),
            "--date",
            "2026_03_08",
            "--keep-intermediate",
            "--yes",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "No category zips" in captured.out
