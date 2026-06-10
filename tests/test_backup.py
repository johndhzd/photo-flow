from datetime import date, datetime, timezone
from pathlib import Path

from photo_flow.backup import (
    BackupPlan,
    archive_name,
    build_archive_command,
    copy_to_existing_destinations,
    create_manifest,
    sha256_file,
)
from photo_flow.models import OutputFormat


def test_archive_name_uses_date_tags_and_extension():
    assert archive_name(date(2026, 6, 10), ("japan", "street"), encrypted=False) == "2026-06-10_japan_street.zip"
    assert archive_name(date(2026, 6, 10), ("private",), encrypted=True) == "2026-06-10_private.7z"
    assert archive_name(date(2026, 6, 10), (), encrypted=False) == "2026-06-10.zip"


def test_archive_name_sanitizes_tags():
    assert archive_name(date(2026, 6, 10), ("private trip", "x/y"), encrypted=False) == "2026-06-10_private_trip_x_y.zip"


def test_sha256_file_hashes_content(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("abc", encoding="utf-8")

    assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_create_manifest_lists_files_and_hashes(tmp_path):
    raw = tmp_path / "DSC0001.ARW"
    raw.write_bytes(b"raw")
    manifest = create_manifest(
        timestamp=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
        output_format=OutputFormat.HEIC,
        quality=90,
        source_dirs={"raw_dir": tmp_path},
        converted_output_dir=tmp_path / "converted",
        backup_destinations=(tmp_path / "backup",),
        files=(raw,),
        tool_versions={"exiftool": "exiftool 13.0"},
        warnings=("missing destination",),
        verification_results=("DSC0001.heic ok",),
    )

    assert manifest["output_format"] == "heic"
    assert manifest["quality"] == 90
    assert manifest["files"][0]["path"] == str(raw)
    assert manifest["files"][0]["sha256"] == sha256_file(raw)


def test_build_archive_command_uses_zip_for_unencrypted(tmp_path):
    plan = BackupPlan(archive_path=tmp_path / "backup.zip", staging_dir=tmp_path / "stage", encrypted=False)

    assert build_archive_command(plan, password=None) == (
        "zip",
        "-r",
        str(tmp_path / "backup.zip"),
        ".",
    )


def test_build_archive_command_uses_7z_for_encrypted(tmp_path):
    plan = BackupPlan(archive_path=tmp_path / "backup.7z", staging_dir=tmp_path / "stage", encrypted=True)

    assert build_archive_command(plan, password="secret") == (
        "7z",
        "a",
        "-t7z",
        "-mhe=on",
        "-psecret",
        str(tmp_path / "backup.7z"),
        ".",
    )


def test_copy_to_existing_destinations_skips_missing_paths(tmp_path):
    archive = tmp_path / "backup.zip"
    archive.write_bytes(b"archive")
    existing = tmp_path / "existing"
    existing.mkdir()
    missing = tmp_path / "missing"

    copied, warnings = copy_to_existing_destinations(archive, (existing, missing))

    assert copied == (existing / "backup.zip",)
    assert (existing / "backup.zip").read_bytes() == b"archive"
    assert warnings == (f"Backup destination does not exist: {missing}",)
