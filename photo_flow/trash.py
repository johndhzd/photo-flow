from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from photo_flow.commands import run_command
from photo_flow.models import CommandResult


def build_trash_command(paths: Sequence[Path]) -> tuple[str, ...]:
    return ("trash", *(str(path) for path in paths))


def trash_files(
    paths: Sequence[Path],
    *,
    runner: Callable[[Sequence[str]], CommandResult] | None = None,
) -> CommandResult:
    command_runner = runner or (lambda args: run_command(args, check=True))
    return command_runner(build_trash_command(paths))
