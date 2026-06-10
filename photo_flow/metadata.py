from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from photo_flow.commands import run_command
from photo_flow.models import CommandResult, ConversionPlan


def build_copy_metadata_command(plan: ConversionPlan) -> tuple[str, ...]:
    return (
        "exiftool",
        "-TagsFromFile",
        str(plan.source_tiff),
        "-all:all",
        "-overwrite_original",
        str(plan.output_file),
    )


def build_read_metadata_command(path: Path) -> tuple[str, ...]:
    return ("exiftool", "-json", str(path))


def copy_metadata(
    plans: Sequence[ConversionPlan],
    *,
    runner: Callable[[Sequence[str]], CommandResult] | None = None,
) -> tuple[CommandResult, ...]:
    command_runner = runner or (lambda args: run_command(args, check=True))
    return tuple(command_runner(build_copy_metadata_command(plan)) for plan in plans)


def read_metadata(
    path: Path,
    *,
    runner: Callable[[Sequence[str]], CommandResult] | None = None,
) -> CommandResult:
    command_runner = runner or (lambda args: run_command(args, check=True))
    return command_runner(build_read_metadata_command(path))
