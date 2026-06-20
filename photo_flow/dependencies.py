from __future__ import annotations

import shutil
from collections.abc import Callable

from photo_flow.models import OutputFormat


def conversion_tools(output_format: OutputFormat) -> tuple[str, ...]:
    converter = "cjxl" if output_format is OutputFormat.JXL else "magick"
    return ("exiftool", "magick", converter)


def bundle_tools(*, encrypt: bool) -> tuple[str, ...]:
    return ("7z",) if encrypt else ()


def missing_tools(
    tools: tuple[str, ...],
    *,
    resolver: Callable[[str], str | None] = shutil.which,
) -> tuple[str, ...]:
    seen: dict[str, None] = dict.fromkeys(tools)
    return tuple(tool for tool in seen if resolver(tool) is None)
