from pathlib import Path

from photo_flow.backup import BackupPlan, build_archive_command
from photo_flow.integrity import build_identify_command


def test_build_identify_command_uses_magick_identify():
    assert build_identify_command(Path("out.heic")) == ("magick", "identify", "out.heic")


def test_build_archive_command_accepts_hidden_password_flag():
    plan = BackupPlan(archive_path=Path("backup.7z"), staging_dir=Path("stage"), encrypted=True)

    assert build_archive_command(plan, password="secret") == (
        "7z",
        "a",
        "-t7z",
        "-mhe=on",
        "-psecret",
        "backup.7z",
        ".",
    )
