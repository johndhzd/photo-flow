import zipfile
from datetime import date

import pytest

from photo_flow.backup import (
    archive_name,
    build_bundle_command,
    bundle_archives,
    zip_files,
)


def test_archive_name_uses_underscore_date_tags_and_extension():
    assert archive_name(date(2026, 3, 8), ("japan", "street"), encrypted=False) == "2026_03_08_japan_street.zip"
    assert archive_name(date(2026, 3, 8), ("private",), encrypted=True) == "2026_03_08_private.7z"
    assert archive_name(date(2026, 3, 8), (), encrypted=False) == "2026_03_08.zip"


def test_archive_name_sanitizes_tags():
    assert archive_name(date(2026, 3, 8), ("private trip", "x/y"), encrypted=False) == "2026_03_08_private_trip_x_y.zip"


def test_zip_files_flattens_names(tmp_path):
    a = tmp_path / "src" / "DSC0001.ARW"
    b = tmp_path / "src" / "DSC0002.ARW"
    a.parent.mkdir(parents=True)
    a.write_bytes(b"one")
    b.write_bytes(b"two")
    dest = tmp_path / "out" / "original_raw.zip"

    zip_files((a, b), dest)

    with zipfile.ZipFile(dest) as archive:
        assert sorted(archive.namelist()) == ["DSC0001.ARW", "DSC0002.ARW"]
        assert archive.read("DSC0001.ARW") == b"one"


def test_zip_files_rejects_duplicate_basenames(tmp_path):
    a = tmp_path / "x" / "DSC0001.ARW"
    b = tmp_path / "y" / "DSC0001.ARW"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_bytes(b"a")
    b.write_bytes(b"b")

    with pytest.raises(ValueError, match="Duplicate file name"):
        zip_files((a, b), tmp_path / "out.zip")


def test_zip_files_rejects_empty_input(tmp_path):
    with pytest.raises(ValueError, match="no files"):
        zip_files((), tmp_path / "out.zip")


def test_bundle_archives_plain_zip_contains_category_zips(tmp_path):
    heic = zip_files((_file(tmp_path, "a.heic"),), tmp_path / "work" / "original_heic.zip")
    edited = zip_files((_file(tmp_path, "b.heic"),), tmp_path / "work" / "edited.zip")
    final = tmp_path / "Backups" / "2026_03_08.zip"

    bundle_archives((heic, edited), final, encrypt=False)

    with zipfile.ZipFile(final) as archive:
        assert sorted(archive.namelist()) == ["edited.zip", "original_heic.zip"]


def test_bundle_archives_encrypted_uses_runner(tmp_path):
    calls = []

    def runner(args):
        calls.append(tuple(args))

        class _Result:
            ok = True

        return _Result()

    heic = zip_files((_file(tmp_path, "a.heic"),), tmp_path / "work" / "original_heic.zip")
    final = tmp_path / "Backups" / "2026_03_08_private.7z"

    bundle_archives((heic,), final, encrypt=True, password="secret", runner=runner)

    assert calls == [build_bundle_command(final, (heic,), password="secret")]


def _file(base, name):
    path = base / "files" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(name.encode())
    return path
