from __future__ import annotations

import argparse
import getpass
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from photo_flow.backup import archive_name, bundle_archives, zip_files
from photo_flow.commands import run_command as run_external_command
from photo_flow.config import ConfigError, load_config
from photo_flow.converter import build_conversion_command, build_conversion_plans
from photo_flow.dependencies import bundle_tools, conversion_tools, missing_tools
from photo_flow.estimator import (
    EstimateResult,
    choose_sample_files,
    estimate_total_size,
    format_bytes,
)
from photo_flow.integrity import identify_image, verify_converted_file
from photo_flow.logging_setup import configure_logging
from photo_flow.metadata import build_copy_metadata_command, read_metadata
from photo_flow.models import ConversionPlan, OutputFormat, RootConfig
from photo_flow.parallel import default_workers, parallel_map
from photo_flow.progress import ProgressBar
from photo_flow.scanner import (
    TIFF_EXTENSIONS,
    files_in,
    original_heic_files,
    processed_files,
    raw_files,
    tiff_files,
)
from photo_flow.sessions import (
    SessionError,
    available_dates,
    list_tiff_dates,
    parse_session_date,
    resolve_raw_folder,
    resolve_session_date,
)


HEIC_ZIP = "original_heic.zip"
RAW_ZIP = "original_raw.zip"
EDITED_ZIP = "edited.zip"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in (None, "tui"):
        try:
            return launch_tui(args)
        except (ConfigError, SessionError, ValueError, RuntimeError) as exc:
            print(f"Error: {exc}")
            return 1
    handlers = {
        "estimate": estimate_command,
        "convert": convert_command,
        "backup-heic": backup_heic_command,
        "backup-raw": backup_raw_command,
        "backup-edited": backup_edited_command,
        "bundle": bundle_command,
        "run": run_command,
    }
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 2
    try:
        return handler(args)
    except (ConfigError, SessionError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}")
        return 1


def launch_tui(args: argparse.Namespace) -> int:
    config_path = getattr(args, "config", None) or Path("config.yaml")
    config = load_config(config_path)
    from photo_flow.tui import run_tui

    return run_tui(config, config_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photo-flow",
        description="Run without a subcommand to open the interactive TUI.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="config file used by the TUI when no subcommand is given (default: config.yaml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    tui = subparsers.add_parser("tui", help="open the interactive terminal UI (default)")
    tui.add_argument("--config", type=Path, default=argparse.SUPPRESS, help="config file")

    estimate = subparsers.add_parser("estimate", help="estimate converted output size for a session")
    _add_config_date(estimate)
    _add_format_quality(estimate)
    estimate.add_argument("--dry-sample-size", type=int, default=0, help=argparse.SUPPRESS)

    convert = subparsers.add_parser("convert", help="convert TIFF exports into the processed folder")
    _add_config_date(convert)
    _add_format_quality(convert)
    convert.add_argument("--overwrite", action="store_true")

    backup_heic = subparsers.add_parser("backup-heic", help="zip original HEIC/HIF files for a session")
    _add_config_date(backup_heic)
    backup_heic.add_argument("--raw", dest="raw_name", help="RawPhotos folder name override")

    backup_raw = subparsers.add_parser("backup-raw", help="zip original RAW files for a session")
    _add_config_date(backup_raw)
    backup_raw.add_argument("--raw", dest="raw_name", help="RawPhotos folder name override")

    backup_edited = subparsers.add_parser(
        "backup-edited", help="zip edited/converted files (auto-converts when missing)"
    )
    _add_config_date(backup_edited)
    _add_format_quality(backup_edited)
    backup_edited.add_argument("--overwrite", action="store_true")

    bundle = subparsers.add_parser("bundle", help="bundle category zips into the final archive")
    _add_config_date(bundle)
    _add_bundle_options(bundle)

    run = subparsers.add_parser("run", help="full pipeline: heic + raw + edited + bundle for a session")
    _add_config_date(run)
    _add_format_quality(run)
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--raw", dest="raw_name", help="RawPhotos folder name override")
    _add_bundle_options(run)

    return parser


def _add_config_date(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--date", dest="session_date", help="session date YYYY_MM_DD")
    parser.add_argument("--yes", action="store_true", help="auto-confirm prompts and skip interactive selection")
    parser.add_argument(
        "-j",
        "--workers",
        type=int,
        default=0,
        help="parallel workers for conversion/verification (0 = auto, 1 = serial)",
    )


def _add_format_quality(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", dest="output_format", choices=["heic", "jpg", "jpeg", "png", "jxl"])
    parser.add_argument("--quality", type=int)


def _add_bundle_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tags", default=None, help="comma-separated tags for the final archive name")
    parser.add_argument("--encrypt", action="store_true", help="create an encrypted .7z archive")
    delete_group = parser.add_mutually_exclusive_group()
    delete_group.add_argument(
        "--delete-intermediate",
        dest="delete_intermediate",
        action="store_true",
        help="delete the Backups/<date> working folder after bundling",
    )
    delete_group.add_argument(
        "--keep-intermediate",
        dest="keep_intermediate",
        action="store_true",
        help="keep the Backups/<date> working folder after bundling",
    )


def resolve_format_and_quality(args: argparse.Namespace, config: RootConfig) -> tuple[OutputFormat, int]:
    output_format = OutputFormat.parse(args.output_format) if args.output_format else config.default_format
    quality = args.quality if args.quality is not None else config.default_quality
    if not 1 <= quality <= 100:
        raise ValueError("quality must be between 1 and 100")
    return output_format, quality


def _start_logging(config: RootConfig) -> Path:
    timestamp = datetime.now(timezone.utc)
    return configure_logging(config.log_dir, timestamp)


def _resolve_workers(args: argparse.Namespace) -> int:
    value = getattr(args, "workers", 0)
    return value if value >= 1 else default_workers()


# --------------------------------------------------------------------------- #
# Core operations (reused by both standalone commands and the run pipeline).
# --------------------------------------------------------------------------- #


def _convert_one(plan: ConversionPlan) -> None:
    run_external_command(build_conversion_command(plan), check=True)


def _verify_one(plan: ConversionPlan) -> None:
    run_external_command(build_copy_metadata_command(plan), check=True)
    errors = verify_converted_file(plan.output_file)
    if errors:
        for error in errors:
            logging.error("%s: %s", error.path, error.reason)
        raise RuntimeError(f"Converted file verification failed: {plan.output_file}")
    read_metadata(plan.output_file)
    identify_image(plan.output_file)
    logging.info("Converted %s -> %s", plan.source_tiff.name, plan.output_file.name)


def do_convert(
    config: RootConfig,
    session_date: str,
    output_format: OutputFormat,
    quality: int,
    *,
    overwrite: bool,
    workers: int = 1,
) -> tuple[Path, ...]:
    tiff_dir = config.tiff_dir_for(session_date)
    tiffs = files_in(tiff_dir, TIFF_EXTENSIONS)
    if not tiffs:
        raise SessionError(f"No TIFF files to convert in {tiff_dir}")

    missing = missing_tools(conversion_tools(output_format))
    if missing:
        raise RuntimeError(f"Missing required tools: {', '.join(missing)}")

    if output_format is OutputFormat.PNG:
        logging.warning("PNG output is lossless; quality setting is ignored by conversion")
        print("Warning: PNG output is lossless; quality setting is ignored.")

    output_dir = config.processed_dir_for(session_date)
    plans = build_conversion_plans(
        tiffs,
        output_dir=output_dir,
        output_format=output_format,
        quality=quality,
        overwrite=overwrite,
    )
    print(f"Converting {len(plans)} TIFF files to {output_format.value} "
          f"in {output_dir} ({workers} workers)")

    parallel_map(
        plans,
        _convert_one,
        workers=workers,
        desc="Converting",
        label_fn=lambda p: p.source_tiff.name,
    )
    parallel_map(
        plans,
        _verify_one,
        workers=workers,
        desc="Verifying ",
        label_fn=lambda p: p.output_file.name,
    )

    return tuple(plan.output_file for plan in plans)


def do_estimate(
    config: RootConfig,
    session_date: str,
    output_format: OutputFormat,
    quality: int,
    *,
    workers: int = 1,
    dry_sample_size: int = 0,
) -> EstimateResult | None:
    """Convert a handful of sample TIFFs and extrapolate the full output size.

    Returns ``None`` when the session has no TIFF files. Shared by the
    ``estimate`` command and the TUI so the sampling logic lives in one place.
    """

    samples_source = tiff_files(config, session_date)
    samples = choose_sample_files(samples_source)
    if not samples:
        return None

    with tempfile.TemporaryDirectory(prefix="photo-flow-estimate-") as temp_dir:
        temp_output_dir = Path(temp_dir)
        plans = build_conversion_plans(
            samples,
            output_dir=temp_output_dir,
            output_format=output_format,
            quality=quality,
            overwrite=True,
        )
        if dry_sample_size:
            for plan in plans:
                plan.output_file.write_bytes(b"x" * dry_sample_size)
        else:
            parallel_map(
                plans,
                _convert_one,
                workers=workers,
                desc="Sampling",
                label_fn=lambda p: p.source_tiff.name,
            )
        return estimate_total_size(
            samples_source,
            samples,
            tuple(plan.output_file for plan in plans),
        )


def do_backup_heic(config: RootConfig, session_date: str, raw_name: str) -> Path:
    files = original_heic_files(config, raw_name)
    if not files:
        raise SessionError(
            f"No original HEIC/HIF files found in {config.raw_folder(raw_name)}"
        )
    dest = config.backup_work_dir(session_date) / HEIC_ZIP
    with ProgressBar(len(files), desc="Packing HEIC") as bar:
        zip_files(files, dest, on_file=bar.advance)
    logging.info("Zipped %d original HEIC files -> %s", len(files), dest)
    print(f"Created {dest} ({len(files)} files)")
    return dest


def do_backup_raw(config: RootConfig, session_date: str, raw_name: str) -> Path:
    files = raw_files(config, raw_name)
    if not files:
        raise SessionError(f"No RAW files found in {config.raw_folder(raw_name)}")
    dest = config.backup_work_dir(session_date) / RAW_ZIP
    with ProgressBar(len(files), desc="Packing RAW ") as bar:
        zip_files(files, dest, on_file=bar.advance)
    logging.info("Zipped %d RAW files -> %s", len(files), dest)
    print(f"Created {dest} ({len(files)} files)")
    return dest


def do_backup_edited(
    config: RootConfig,
    session_date: str,
    output_format: OutputFormat,
    quality: int,
    *,
    overwrite: bool,
    workers: int = 1,
) -> Path:
    files = processed_files(config, session_date)
    if not files:
        print(
            f"No edited files in {config.processed_dir_for(session_date)}; "
            "converting from TIFF exports first."
        )
        do_convert(config, session_date, output_format, quality, overwrite=overwrite, workers=workers)
        files = processed_files(config, session_date)
    if not files:
        raise SessionError(
            f"No edited files available for {session_date} after conversion attempt"
        )
    dest = config.backup_work_dir(session_date) / EDITED_ZIP
    with ProgressBar(len(files), desc="Packing edited") as bar:
        zip_files(files, dest, on_file=bar.advance)
    logging.info("Zipped %d edited files -> %s", len(files), dest)
    print(f"Created {dest} ({len(files)} files)")
    return dest


def do_bundle(
    config: RootConfig,
    session_date: str,
    *,
    tags: tuple[str, ...],
    encrypt: bool,
    delete_intermediate: bool,
    password: str | None = None,
) -> Path:
    work_dir = config.backup_work_dir(session_date)
    candidates = [work_dir / HEIC_ZIP, work_dir / RAW_ZIP, work_dir / EDITED_ZIP]
    existing = [path for path in candidates if path.exists()]
    if not existing:
        raise SessionError(
            f"No category zips found in {work_dir}; run backup-heic/backup-raw/backup-edited first"
        )

    run_date = parse_session_date(session_date)
    final_archive = config.backups_dir / archive_name(run_date, tags, encrypted=encrypt)

    if encrypt:
        missing = missing_tools(bundle_tools(encrypt=True))
        if missing:
            raise RuntimeError(f"Missing required tools: {', '.join(missing)}")
        if password is None:
            password = prompt_password()
    else:
        password = None

    with ProgressBar(len(existing), desc="Bundling") as bar:
        bundle_archives(existing, final_archive, encrypt=encrypt, password=password, on_file=bar.advance)
    logging.info("Bundled %d archives -> %s", len(existing), final_archive)
    print(f"Bundle created: {final_archive}")
    for path in existing:
        print(f"  included: {path.name}")

    if delete_intermediate:
        shutil.rmtree(work_dir)
        logging.info("Deleted intermediate folder: %s", work_dir)
        print(f"Deleted intermediate folder: {work_dir}")
    return final_archive


# --------------------------------------------------------------------------- #
# Command handlers.
# --------------------------------------------------------------------------- #


def estimate_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output_format, quality = resolve_format_and_quality(args, config)
    workers = _resolve_workers(args)
    session_date = resolve_session_date(
        config,
        args.session_date,
        candidates=list_tiff_dates(config),
        assume_yes=args.yes,
        input_fn=input,
        output_fn=print,
    )
    result = do_estimate(
        config,
        session_date,
        output_format,
        quality,
        workers=workers,
        dry_sample_size=args.dry_sample_size,
    )
    if result is None:
        print(f"No TIFF files found in {config.tiff_dir_for(session_date)}.")
        return 0

    print(f"Session: {session_date}")
    print(f"Format: {output_format.value}")
    print(f"Quality: {quality}")
    print(f"Sample files: {result.sample_count}")
    print(f"Sample input size: {format_bytes(result.sample_input_bytes)}")
    print(f"Sample output size: {format_bytes(result.sample_output_bytes)}")
    print(f"Estimated converted output size: {format_bytes(result.estimated_output_bytes)}")
    return 0


def convert_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output_format, quality = resolve_format_and_quality(args, config)
    workers = _resolve_workers(args)
    session_date = resolve_session_date(
        config,
        args.session_date,
        candidates=list_tiff_dates(config),
        assume_yes=args.yes,
        input_fn=input,
        output_fn=print,
    )
    overwrite = args.overwrite or config.overwrite_existing
    _start_logging(config)
    outputs = do_convert(config, session_date, output_format, quality, overwrite=overwrite, workers=workers)
    print(f"Converted {len(outputs)} files into {config.processed_dir_for(session_date)}")
    return 0


def backup_heic_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    session_date = resolve_session_date(
        config,
        args.session_date,
        candidates=available_dates(config),
        assume_yes=args.yes,
        input_fn=input,
        output_fn=print,
    )
    raw_name = resolve_raw_folder(
        config,
        session_date,
        args.raw_name,
        assume_yes=args.yes,
        input_fn=input,
        output_fn=print,
    )
    _start_logging(config)
    do_backup_heic(config, session_date, raw_name)
    return 0


def backup_raw_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    session_date = resolve_session_date(
        config,
        args.session_date,
        candidates=available_dates(config),
        assume_yes=args.yes,
        input_fn=input,
        output_fn=print,
    )
    raw_name = resolve_raw_folder(
        config,
        session_date,
        args.raw_name,
        assume_yes=args.yes,
        input_fn=input,
        output_fn=print,
    )
    _start_logging(config)
    do_backup_raw(config, session_date, raw_name)
    return 0


def backup_edited_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output_format, quality = resolve_format_and_quality(args, config)
    workers = _resolve_workers(args)
    session_date = resolve_session_date(
        config,
        args.session_date,
        candidates=available_dates(config),
        assume_yes=args.yes,
        input_fn=input,
        output_fn=print,
    )
    overwrite = args.overwrite or config.overwrite_existing
    _start_logging(config)
    do_backup_edited(config, session_date, output_format, quality, overwrite=overwrite, workers=workers)
    return 0


def bundle_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    session_date = resolve_session_date(
        config,
        args.session_date,
        candidates=available_dates(config),
        assume_yes=args.yes,
        input_fn=input,
        output_fn=print,
    )
    tags = resolve_tags(args, assume_yes=args.yes)
    encrypt = resolve_encrypt(args, assume_yes=args.yes)
    delete_intermediate = resolve_delete(args, session_date, assume_yes=args.yes)
    _start_logging(config)
    do_bundle(
        config,
        session_date,
        tags=tags,
        encrypt=encrypt,
        delete_intermediate=delete_intermediate,
    )
    return 0


def run_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output_format, quality = resolve_format_and_quality(args, config)
    workers = _resolve_workers(args)
    session_date = resolve_session_date(
        config,
        args.session_date,
        candidates=available_dates(config),
        assume_yes=args.yes,
        input_fn=input,
        output_fn=print,
    )
    raw_name = resolve_raw_folder(
        config,
        session_date,
        args.raw_name,
        assume_yes=args.yes,
        input_fn=input,
        output_fn=print,
    )
    overwrite = args.overwrite or config.overwrite_existing
    tags = resolve_tags(args, assume_yes=args.yes)
    encrypt = resolve_encrypt(args, assume_yes=args.yes)
    delete_intermediate = resolve_delete(args, session_date, assume_yes=args.yes)

    _start_logging(config)
    logging.info("Starting photo-flow run for %s (raw folder %s)", session_date, raw_name)
    do_backup_heic(config, session_date, raw_name)
    do_backup_raw(config, session_date, raw_name)
    do_backup_edited(config, session_date, output_format, quality, overwrite=overwrite, workers=workers)
    do_bundle(
        config,
        session_date,
        tags=tags,
        encrypt=encrypt,
        delete_intermediate=delete_intermediate,
    )
    return 0


# --------------------------------------------------------------------------- #
# Prompt helpers.
# --------------------------------------------------------------------------- #


def parse_tags(value: str) -> tuple[str, ...]:
    return tuple(tag.strip() for tag in value.split(",") if tag.strip())


def resolve_tags(args: argparse.Namespace, *, assume_yes: bool) -> tuple[str, ...]:
    if args.tags is not None:
        return parse_tags(args.tags)
    if assume_yes:
        return ()
    return parse_tags(input("Tags (comma-separated, blank for none): "))


def resolve_encrypt(args: argparse.Namespace, *, assume_yes: bool) -> bool:
    if args.encrypt:
        return True
    if assume_yes:
        return False
    return confirm("Encrypt the final archive?", assume_yes=False)


def resolve_delete(args: argparse.Namespace, session_date: str, *, assume_yes: bool) -> bool:
    if getattr(args, "delete_intermediate", False):
        return True
    if getattr(args, "keep_intermediate", False):
        return False
    if assume_yes:
        return False
    return confirm(
        f"Delete the intermediate Backups/{session_date} folder after bundling?",
        assume_yes=False,
    )


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
