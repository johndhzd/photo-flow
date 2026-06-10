from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Sequence

from photo_flow.config import ConfigError, load_config
from photo_flow.converter import build_conversion_plans, convert_all
from photo_flow.estimator import choose_sample_files, estimate_total_size, format_bytes
from photo_flow.models import OutputFormat
from photo_flow.scanner import ScanError, scan_session


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
    raise RuntimeError("run command is unavailable until Task 12")
