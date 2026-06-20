import sys

import pytest

from photo_flow.commands import CommandError, run_command
from photo_flow.dependencies import bundle_tools, conversion_tools, missing_tools
from photo_flow.models import OutputFormat


def test_conversion_tools_for_heic_uses_magick():
    assert conversion_tools(OutputFormat.HEIC) == ("exiftool", "magick", "magick")


def test_conversion_tools_for_jxl_uses_cjxl():
    assert conversion_tools(OutputFormat.JXL) == ("exiftool", "magick", "cjxl")


def test_bundle_tools_requires_7z_only_when_encrypting():
    assert bundle_tools(encrypt=True) == ("7z",)
    assert bundle_tools(encrypt=False) == ()


def test_missing_tools_reports_only_absent_tools():
    calls = {"exiftool": "/opt/homebrew/bin/exiftool", "magick": None}

    assert missing_tools(("exiftool", "magick"), resolver=calls.get) == ("magick",)


def test_run_command_supports_cwd(tmp_path):
    result = run_command(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; print(Path.cwd().name)",
        ],
        cwd=tmp_path,
    )

    assert result.ok is True
    assert result.stdout.strip() == tmp_path.name


def test_run_command_raises_command_error_when_check_enabled():
    with pytest.raises(CommandError):
        run_command([sys.executable, "-c", "raise SystemExit(3)"])
