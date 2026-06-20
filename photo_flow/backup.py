from __future__ import annotations

import zipfile
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from photo_flow.commands import run_command
from photo_flow.models import CommandResult


CategoryRunner = Callable[[Sequence[str]], CommandResult]


def archive_name(run_date: date, tags: Sequence[str], *, encrypted: bool) -> str:
    """Final bundle name like ``2026_03_08_japan_street.zip``.

    Uses underscore-separated dates to match the on-disk session folder naming.
    """

    clean_tags = tuple(_clean_tag(tag) for tag in tags if _clean_tag(tag))
    suffix = ".7z" if encrypted else ".zip"
    stamp = f"{run_date:%Y_%m_%d}"
    if clean_tags:
        return f"{stamp}_{'_'.join(clean_tags)}{suffix}"
    return f"{stamp}{suffix}"


def _clean_tag(tag: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in tag.strip())


def zip_files(files: Sequence[Path], dest_zip: Path, *, compress: bool = False) -> Path:
    """Write ``files`` into ``dest_zip`` with flattened (basename) entries.

    Defaults to stored (uncompressed) entries because raw, HEIF and converted
    photos are already compressed; deflating them wastes time for no gain.
    """

    if not files:
        raise ValueError("Cannot create a zip with no files")
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    if dest_zip.exists():
        dest_zip.unlink()
    compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    seen: set[str] = set()
    with zipfile.ZipFile(dest_zip, "w", compression, allowZip64=True) as archive:
        for source in files:
            arcname = source.name
            if arcname in seen:
                raise ValueError(f"Duplicate file name in archive: {arcname}")
            seen.add(arcname)
            archive.write(source, arcname=arcname)
    return dest_zip


def build_bundle_command(
    final_archive: Path,
    files: Sequence[Path],
    *,
    password: str | None,
) -> tuple[str, ...]:
    if not password:
        raise ValueError("Encrypted bundles require a password")
    return (
        "7z",
        "a",
        "-t7z",
        "-mhe=on",
        f"-p{password}",
        str(final_archive),
        *(str(path) for path in files),
    )


def bundle_archives(
    category_zips: Sequence[Path],
    final_archive: Path,
    *,
    encrypt: bool,
    password: str | None = None,
    runner: CategoryRunner | None = None,
) -> Path:
    """Combine the per-category zips into a single final archive.

    Unencrypted bundles are plain (stored) zips. Encrypted bundles delegate to
    ``7z`` with header encryption enabled.
    """

    if not category_zips:
        raise ValueError("No category archives to bundle")
    final_archive.parent.mkdir(parents=True, exist_ok=True)
    if final_archive.exists():
        final_archive.unlink()

    if encrypt:
        command_runner = runner or (lambda args: run_command(args, check=True))
        command_runner(build_bundle_command(final_archive, category_zips, password=password))
        return final_archive

    seen: set[str] = set()
    with zipfile.ZipFile(final_archive, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
        for source in category_zips:
            arcname = source.name
            if arcname in seen:
                raise ValueError(f"Duplicate file name in bundle: {arcname}")
            seen.add(arcname)
            archive.write(source, arcname=arcname)
    return final_archive
