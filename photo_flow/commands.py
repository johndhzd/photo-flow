from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from photo_flow.models import CommandResult


class CommandError(RuntimeError):
    def __init__(self, result: CommandResult):
        self.result = result
        command = " ".join(result.args)
        super().__init__(f"Command failed ({result.returncode}): {command}\n{result.stderr}")


def run_command(
    args: Sequence[str],
    *,
    check: bool = True,
    cwd: Path | None = None,
) -> CommandResult:
    completed = subprocess.run(
        list(args),
        check=False,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = CommandResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and not result.ok:
        raise CommandError(result)
    return result
