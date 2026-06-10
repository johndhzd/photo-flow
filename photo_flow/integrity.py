from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from photo_flow.commands import run_command
from photo_flow.models import CommandResult


@dataclass(frozen=True)
class IntegrityError:
    path: Path
    reason: str


def build_identify_command(path: Path) -> tuple[str, ...]:
    return ("magick", "identify", str(path))


def verify_converted_file(path: Path) -> tuple[IntegrityError, ...]:
    if not path.exists():
        return (IntegrityError(path=path, reason="file is missing"),)
    if not path.is_file():
        return (IntegrityError(path=path, reason="path is not a file"),)
    if path.stat().st_size <= 0:
        return (IntegrityError(path=path, reason="file is empty"),)
    return ()


def identify_image(
    path: Path,
    *,
    runner: Callable[[Sequence[str]], CommandResult] | None = None,
) -> CommandResult:
    command_runner = runner or (lambda args: run_command(args, check=True))
    return command_runner(build_identify_command(path))
