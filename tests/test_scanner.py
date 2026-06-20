from _helpers import build_root_config, touch

from photo_flow.scanner import (
    files_in,
    original_heic_files,
    processed_files,
    raw_files,
    tiff_files,
)


def test_raw_and_heic_files_split_by_extension(tmp_path):
    config = build_root_config(tmp_path)
    folder = config.raw_folder("10460308")
    touch(folder / "DSC0002.ARW")
    touch(folder / "DSC0001.cr3")
    touch(folder / "DSC0001.HIF")
    touch(folder / "DSC0002.HEIC")
    touch(folder / "ignore.txt")

    assert [p.name for p in raw_files(config, "10460308")] == ["DSC0001.cr3", "DSC0002.ARW"]
    assert [p.name for p in original_heic_files(config, "10460308")] == [
        "DSC0001.HIF",
        "DSC0002.HEIC",
    ]


def test_tiff_and_processed_files(tmp_path):
    config = build_root_config(tmp_path)
    touch(config.tiff_dir_for("2026_03_08") / "DSC0001.tif")
    touch(config.tiff_dir_for("2026_03_08") / "DSC0002.TIFF")
    touch(config.processed_dir_for("2026_03_08") / "DSC0001.heic")
    touch(config.processed_dir_for("2026_03_08") / "DSC0002.jpg")

    assert [p.name for p in tiff_files(config, "2026_03_08")] == ["DSC0001.tif", "DSC0002.TIFF"]
    assert [p.name for p in processed_files(config, "2026_03_08")] == [
        "DSC0001.heic",
        "DSC0002.jpg",
    ]


def test_files_in_returns_empty_for_missing_directory(tmp_path):
    assert files_in(tmp_path / "nope", (".tif",)) == ()
