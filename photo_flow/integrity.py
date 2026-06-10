from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IntegrityError:
    path: Path
    reason: str


def verify_converted_file(path: Path) -> tuple[IntegrityError, ...]:
    if not path.exists():
        return (IntegrityError(path=path, reason="file is missing"),)
    if not path.is_file():
        return (IntegrityError(path=path, reason="path is not a file"),)
    if path.stat().st_size <= 0:
        return (IntegrityError(path=path, reason="file is empty"),)
    return ()
