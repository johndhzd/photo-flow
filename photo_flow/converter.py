from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from photo_flow.commands import run_command
from photo_flow.models import CommandResult, ConversionPlan, OutputFormat, format_extension


class ConversionError(RuntimeError):
    pass


def build_conversion_plans(
    tiff_files: Sequence[Path],
    *,
    output_dir: Path,
    output_format: OutputFormat,
    quality: int,
    overwrite: bool,
) -> tuple[ConversionPlan, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plans: list[ConversionPlan] = []
    for tiff_file in tiff_files:
        output_file = output_dir / f"{tiff_file.stem}{format_extension(output_format)}"
        if output_file.exists() and not overwrite:
            raise ConversionError(f"Output file already exists: {output_file}")
        plans.append(ConversionPlan(tiff_file, output_file, output_format, quality))
    return tuple(plans)


def build_conversion_command(plan: ConversionPlan) -> tuple[str, ...]:
    if plan.output_format is OutputFormat.JXL:
        return ("cjxl", str(plan.source_tiff), str(plan.output_file), "-q", str(plan.quality))
    if plan.output_format is OutputFormat.PNG:
        return ("magick", str(plan.source_tiff), str(plan.output_file))
    return (
        "magick",
        str(plan.source_tiff),
        "-quality",
        str(plan.quality),
        str(plan.output_file),
    )


def convert_all(
    plans: Sequence[ConversionPlan],
    *,
    runner: Callable[[Sequence[str]], CommandResult] | None = None,
) -> tuple[CommandResult, ...]:
    command_runner = runner or (lambda args: run_command(args, check=True))
    results: list[CommandResult] = []
    for plan in plans:
        results.append(command_runner(build_conversion_command(plan)))
    return tuple(results)
