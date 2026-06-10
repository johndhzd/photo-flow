from __future__ import annotations

import argparse
import getpass
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from photo_flow.backup import (
    BackupPlan,
    archive_name,
    build_archive_command,
    copy_to_existing_destinations,
    create_manifest,
    stage_backup_files,
    write_manifest,
)
from photo_flow.commands import run_command as run_external_command
from photo_flow.config import ConfigError, load_config
from photo_flow.converter import build_conversion_plans, convert_all
from photo_flow.dependencies import missing_tools, required_tools_for
from photo_flow.estimator import choose_sample_files, estimate_total_size, format_bytes
from photo_flow.integrity import verify_converted_file
from photo_flow.logging_setup import configure_logging
from photo_flow.metadata import copy_metadata, read_metadata
from photo_flow.models import OutputFormat
from photo_flow.scanner import ScanError, scan_session
from photo_flow.trash import trash_files


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "estimate":
            return estimate_command(args)
        if args.command == "run":
            return run_command(args)
    except (ConfigError, ScanError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}")
        return 1
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="photo-flow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    estimate = subparsers.add_parser("estimate", help="estimate converted output size")
    add_common_options(estimate)
    estimate.add_argument("--dry-sample-size", type=int, default=0, help=argparse.SUPPRESS)

    run = subparsers.add_parser("run", help="run conversion, cleanup, and backup workflow")
    add_common_options(run)
    run.add_argument("--tags", default="", help="comma-separated tags for the backup name")
    run.add_argument("--encrypt", action="store_true", help="create encrypted .7z backup")
    run.add_argument("--yes", action="store_true", help="auto-confirm non-destructive prompts")
    run.add_argument("--dry-run", action="store_true", help="print planned work without external tool execution")
    return parser


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--format", dest="output_format", choices=["heic", "jpg", "jpeg", "png", "jxl"])
    parser.add_argument("--quality", type=int)
    parser.add_argument("--overwrite", action="store_true")


def resolve_format_and_quality(args: argparse.Namespace, config) -> tuple[OutputFormat, int]:
    output_format = OutputFormat.parse(args.output_format) if args.output_format else config.default_format
    quality = args.quality if args.quality is not None else config.default_quality
    if not 1 <= quality <= 100:
        raise ValueError("quality must be between 1 and 100")
    return output_format, quality


def estimate_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output_format, quality = resolve_format_and_quality(args, config)
    inventory = scan_session(config)
    samples = choose_sample_files(inventory.tiff_files)
    if not samples:
        print("No TIFF files found.")
        return 0

    with tempfile.TemporaryDirectory(prefix="photo-flow-estimate-") as temp_dir:
        temp_output_dir = Path(temp_dir)
        plans = build_conversion_plans(
            samples,
            output_dir=temp_output_dir,
            output_format=output_format,
            quality=quality,
            overwrite=True,
        )
        if args.dry_sample_size:
            for plan in plans:
                plan.output_file.write_bytes(b"x" * args.dry_sample_size)
        else:
            convert_all(plans)
        result = estimate_total_size(
            inventory.tiff_files,
            samples,
            tuple(plan.output_file for plan in plans),
        )

    print(f"Format: {output_format.value}")
    print(f"Quality: {quality}")
    print(f"Sample files: {result.sample_count}")
    print(f"Sample input size: {format_bytes(result.sample_input_bytes)}")
    print(f"Sample output size: {format_bytes(result.sample_output_bytes)}")
    print(f"Estimated converted output size: {format_bytes(result.estimated_output_bytes)}")
    return 0


def run_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output_format, quality = resolve_format_and_quality(args, config)
    inventory = scan_session(config)
    overwrite = args.overwrite or config.overwrite_existing
    plans = build_conversion_plans(
        inventory.tiff_files,
        output_dir=config.converted_output_dir,
        output_format=output_format,
        quality=quality,
        overwrite=overwrite,
    )
    tags = tuple(tag.strip() for tag in args.tags.split(",") if tag.strip())

    if args.dry_run:
        print("Dry run completed. Planned converted files:")
        for plan in plans:
            print(f"- {plan.source_tiff.name} -> {plan.output_file.name}")
        return 0

    missing = missing_tools(required_tools_for(output_format, encrypted_backup=args.encrypt))
    if missing:
        raise RuntimeError(f"Missing required tools: {', '.join(missing)}")

    timestamp = datetime.now(timezone.utc)
    log_path = configure_logging(config.log_dir, timestamp)
    logging.info("Starting photo-flow run")

    if output_format is OutputFormat.PNG:
        logging.warning("PNG output is lossless; quality setting is ignored by conversion")
        print("Warning: PNG output is lossless; quality setting is ignored.")

    if not confirm(f"Convert {len(plans)} TIFF files to {output_format.value}?", assume_yes=args.yes):
        print("Conversion cancelled.")
        return 1

    convert_all(plans)
    copy_metadata(plans)

    verification_messages: list[str] = []
    for plan in plans:
        errors = verify_converted_file(plan.output_file)
        if errors:
            for error in errors:
                logging.error("%s: %s", error.path, error.reason)
            raise RuntimeError("Converted file verification failed")
        read_metadata(plan.output_file)
        verification_messages.append(f"{plan.output_file.name} ok")

    if confirm(f"Move {len(inventory.tiff_files)} TIFF files to macOS Trash?", assume_yes=False):
        trash_files(inventory.tiff_files)
        for path in inventory.tiff_files:
            logging.info("Trashed TIFF: %s", path)

    archive_password = prompt_password() if args.encrypt else None
    local_archive = config.log_dir / archive_name(timestamp.date(), tags, encrypted=args.encrypt)

    with tempfile.TemporaryDirectory(prefix="photo-flow-backup-") as staging:
        staging_dir = Path(staging)
        converted_files = tuple(plan.output_file for plan in plans)
        files_to_hash = (*inventory.raw_files, *inventory.original_heic_files, *converted_files, log_path)
        manifest = create_manifest(
            timestamp=timestamp,
            output_format=output_format,
            quality=quality,
            source_dirs={
                "raw_dir": config.raw_dir,
                "original_heic_dir": config.original_heic_dir,
                "tiff_dir": config.tiff_dir,
            },
            converted_output_dir=config.converted_output_dir,
            backup_destinations=config.backup_destinations,
            files=files_to_hash,
            tool_versions={},
            warnings=(),
            verification_results=tuple(verification_messages),
        )
        write_manifest(staging_dir / "manifest.json", manifest)
        stage_backup_files(
            staging_dir,
            raw_files=inventory.raw_files,
            original_heic_files=inventory.original_heic_files,
            converted_files=converted_files,
            log_path=log_path,
        )
        if args.encrypt:
            backup_plan = BackupPlan(archive_path=local_archive, staging_dir=staging_dir, encrypted=True)
            run_external_command(build_archive_command(backup_plan, password=archive_password), check=True, cwd=staging_dir)
        else:
            shutil.make_archive(str(local_archive.with_suffix("")), "zip", staging_dir)
        copied, warnings = copy_to_existing_destinations(local_archive, config.backup_destinations)
        for warning in warnings:
            logging.warning(warning)
            print(f"Warning: {warning}")

    print(f"Backup created: {local_archive}")
    for path in copied:
        print(f"Backup copied: {path}")
    return 0


def confirm(prompt: str, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    response = input(f"{prompt} [y/N] ").strip().lower()
    return response in {"y", "yes"}


def prompt_password() -> str:
    first = getpass.getpass("Backup password: ")
    second = getpass.getpass("Confirm backup password: ")
    if first != second:
        raise RuntimeError("Backup passwords do not match")
    if not first:
        raise RuntimeError("Backup password cannot be empty")
    return first
