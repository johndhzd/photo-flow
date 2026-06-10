from pathlib import Path

from photo_flow.integrity import IntegrityError, verify_converted_file
from photo_flow.metadata import build_copy_metadata_command, build_read_metadata_command
from photo_flow.models import ConversionPlan, OutputFormat


def test_copy_metadata_command_preserves_original_output_file():
    plan = ConversionPlan(Path("source.tif"), Path("out.heic"), OutputFormat.HEIC, 90)

    assert build_copy_metadata_command(plan) == (
        "exiftool",
        "-TagsFromFile",
        "source.tif",
        "-all:all",
        "-overwrite_original",
        "out.heic",
    )


def test_read_metadata_command_uses_json_output():
    assert build_read_metadata_command(Path("out.heic")) == ("exiftool", "-json", "out.heic")


def test_verify_converted_file_reports_missing_file(tmp_path):
    errors = verify_converted_file(tmp_path / "missing.heic")

    assert errors == (IntegrityError(path=tmp_path / "missing.heic", reason="file is missing"),)


def test_verify_converted_file_reports_empty_file(tmp_path):
    output = tmp_path / "empty.heic"
    output.write_bytes(b"")

    errors = verify_converted_file(output)

    assert errors == (IntegrityError(path=output, reason="file is empty"),)


def test_verify_converted_file_passes_non_empty_file(tmp_path):
    output = tmp_path / "ok.heic"
    output.write_bytes(b"image")

    assert verify_converted_file(output) == ()
