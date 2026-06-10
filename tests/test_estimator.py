from pathlib import Path

from photo_flow.estimator import EstimateResult, choose_sample_files, estimate_total_size, format_bytes


def make_file(path: Path, size: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_choose_sample_files_spreads_across_list(tmp_path):
    files = []
    for index in range(10):
        path = tmp_path / f"{index:02d}.tif"
        make_file(path, 10)
        files.append(path)

    sample = choose_sample_files(tuple(files), max_samples=5)

    assert [item.name for item in sample] == ["00.tif", "02.tif", "04.tif", "07.tif", "09.tif"]


def test_choose_sample_files_returns_all_files_when_under_limit(tmp_path):
    files = []
    for index in range(3):
        path = tmp_path / f"{index:02d}.tif"
        make_file(path, 10)
        files.append(path)

    assert choose_sample_files(tuple(files), max_samples=5) == tuple(files)


def test_estimate_total_size_extrapolates_from_sample_sizes(tmp_path):
    all_files = []
    for index, size in enumerate([100, 200, 300, 400]):
        path = tmp_path / f"{index}.tif"
        make_file(path, size)
        all_files.append(path)
    sample_outputs = []
    for index, size in enumerate([10, 20]):
        path = tmp_path / f"out-{index}.heic"
        make_file(path, size)
        sample_outputs.append(path)

    result = estimate_total_size(tuple(all_files), tuple(all_files[:2]), tuple(sample_outputs))

    assert result == EstimateResult(
        sample_count=2,
        sample_input_bytes=300,
        sample_output_bytes=30,
        total_input_bytes=1000,
        estimated_output_bytes=100,
    )


def test_format_bytes_uses_readable_units():
    assert format_bytes(512) == "512 B"
    assert format_bytes(1536) == "1.5 KB"
