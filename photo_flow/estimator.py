from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EstimateResult:
    sample_count: int
    sample_input_bytes: int
    sample_output_bytes: int
    total_input_bytes: int
    estimated_output_bytes: int


def choose_sample_files(files: tuple[Path, ...], *, max_samples: int = 5) -> tuple[Path, ...]:
    if len(files) <= max_samples:
        return files
    if max_samples <= 1:
        return (files[0],)

    last_index = len(files) - 1
    indexes = [round(index * last_index / (max_samples - 1)) for index in range(max_samples)]
    return tuple(files[index] for index in indexes)


def estimate_total_size(
    all_input_files: tuple[Path, ...],
    sample_input_files: tuple[Path, ...],
    sample_output_files: tuple[Path, ...],
) -> EstimateResult:
    sample_input_bytes = sum(path.stat().st_size for path in sample_input_files)
    sample_output_bytes = sum(path.stat().st_size for path in sample_output_files)
    total_input_bytes = sum(path.stat().st_size for path in all_input_files)
    if sample_input_bytes == 0:
        estimated = 0
    else:
        estimated = round(total_input_bytes * (sample_output_bytes / sample_input_bytes))
    return EstimateResult(
        sample_count=len(sample_input_files),
        sample_input_bytes=sample_input_bytes,
        sample_output_bytes=sample_output_bytes,
        total_input_bytes=total_input_bytes,
        estimated_output_bytes=estimated,
    )


def format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{value} B"
