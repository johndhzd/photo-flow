import sys

import pytest

from photo_flow.commands import CommandError, run_command
from photo_flow.dependencies import missing_tools, required_tools_for
from photo_flow.models import OutputFormat


def test_required_tools_for_heic_includes_metadata_and_trash_tools():
    tools = required_tools_for(OutputFormat.HEIC, encrypted_backup=True)

    assert tools == ("exiftool", "magick", "7z", "trash")


def test_required_tools_for_jxl_uses_cjxl():
    tools = required_tools_for(OutputFormat.JXL, encrypted_backup=False)

    assert tools == ("exiftool", "cjxl", "zip", "trash")


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
