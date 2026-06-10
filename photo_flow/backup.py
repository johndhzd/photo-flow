from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from photo_flow.models import OutputFormat


@dataclass(frozen=True)
class BackupPlan:
    archive_path: Path
    staging_dir: Path
    encrypted: bool


def archive_name(run_date: date, tags: Sequence[str], *, encrypted: bool) -> str:
    clean_tags = tuple(_clean_tag(tag) for tag in tags if _clean_tag(tag))
    suffix = ".7z" if encrypted else ".zip"
    if clean_tags:
        return f"{run_date.isoformat()}_{'_'.join(clean_tags)}{suffix}"
    return f"{run_date.isoformat()}{suffix}"


def _clean_tag(tag: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in tag.strip())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_manifest(
    *,
    timestamp: datetime,
    output_format: OutputFormat,
    quality: int,
    source_dirs: Mapping[str, Path],
    converted_output_dir: Path,
    backup_destinations: Sequence[Path],
    files: Sequence[Path],
    tool_versions: Mapping[str, str],
    warnings: Sequence[str],
    verification_results: Sequence[str],
) -> dict[str, object]:
    return {
        "timestamp": timestamp.isoformat(),
        "output_format": output_format.value,
        "quality": quality,
        "source_dirs": {key: str(value) for key, value in source_dirs.items()},
        "converted_output_dir": str(converted_output_dir),
        "backup_destinations": [str(path) for path in backup_destinations],
        "tool_versions": dict(tool_versions),
        "warnings": list(warnings),
        "verification_results": list(verification_results),
        "files": [
            {
                "path": str(path),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }


def write_manifest(path: Path, manifest: Mapping[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def stage_backup_files(
    staging_dir: Path,
    *,
    raw_files: Sequence[Path],
    original_heic_files: Sequence[Path],
    converted_files: Sequence[Path],
    log_path: Path,
) -> tuple[Path, ...]:
    staged: list[Path] = []
    groups = (
        ("raw", raw_files),
        ("original_heic", original_heic_files),
        ("converted", converted_files),
        ("logs", (log_path,)),
    )
    for directory_name, files in groups:
        target_dir = staging_dir / directory_name
        target_dir.mkdir(parents=True, exist_ok=True)
        for source in files:
            target = target_dir / source.name
            shutil.copy2(source, target)
            staged.append(target)
    return tuple(staged)


def build_archive_command(plan: BackupPlan, *, password: str | None) -> tuple[str, ...]:
    if plan.encrypted:
        if not password:
            raise ValueError("Encrypted backups require a password")
        return ("7z", "a", "-t7z", "-mhe=on", f"-p{password}", str(plan.archive_path), ".")
    return ("zip", "-r", str(plan.archive_path), ".")


def copy_to_existing_destinations(
    archive_path: Path,
    destinations: Sequence[Path],
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    copied: list[Path] = []
    warnings: list[str] = []
    for destination in destinations:
        if not destination.exists() or not destination.is_dir():
            warnings.append(f"Backup destination does not exist: {destination}")
            continue
        target = destination / archive_path.name
        shutil.copy2(archive_path, target)
        copied.append(target)
    return tuple(copied), tuple(warnings)
