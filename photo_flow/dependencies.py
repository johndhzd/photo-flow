from __future__ import annotations

import shutil
from collections.abc import Callable

from photo_flow.models import OutputFormat


def required_tools_for(output_format: OutputFormat, *, encrypted_backup: bool) -> tuple[str, ...]:
    conversion_tool = "cjxl" if output_format is OutputFormat.JXL else "magick"
    archive_tool = "7z" if encrypted_backup else "zip"
    return ("exiftool", conversion_tool, archive_tool, "trash")


def missing_tools(
    tools: tuple[str, ...],
    *,
    resolver: Callable[[str], str | None] = shutil.which,
) -> tuple[str, ...]:
    return tuple(tool for tool in tools if resolver(tool) is None)
