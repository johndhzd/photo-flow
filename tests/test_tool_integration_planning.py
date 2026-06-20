from pathlib import Path

from photo_flow.backup import build_bundle_command
from photo_flow.integrity import build_identify_command


def test_build_identify_command_uses_magick_identify():
    assert build_identify_command(Path("out.heic")) == ("magick", "identify", "out.heic")


def test_build_bundle_command_uses_7z_with_header_encryption():
    command = build_bundle_command(
        Path("2026_03_08_private.7z"),
        (Path("original_heic.zip"), Path("edited.zip")),
        password="secret",
    )

    assert command == (
        "7z",
        "a",
        "-t7z",
        "-mhe=on",
        "-psecret",
        "2026_03_08_private.7z",
        "original_heic.zip",
        "edited.zip",
    )
