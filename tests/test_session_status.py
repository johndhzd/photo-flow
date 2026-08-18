from photo_flow.session_status import build_session_status, match_raw_folder


def test_build_session_status_counts_and_zip_presence(make_root_config, touch_file, tmp_path):
    config = make_root_config(tmp_path / "root")
    touch_file(config.tiff_dir_for("2026_03_08") / "a.tif")
    touch_file(config.tiff_dir_for("2026_03_08") / "b.tif")
    touch_file(config.processed_dir_for("2026_03_08") / "a.heic")
    touch_file(config.raw_folder("10460308") / "x.arw")
    touch_file(config.raw_folder("10460308") / "y.hif")
    touch_file(config.backup_work_dir("2026_03_08") / "original_heic.zip")

    status = build_session_status(config, "2026_03_08")

    assert status.tiff_count == 2
    assert status.processed_count == 1
    assert status.raw_name == "10460308"
    assert status.raw_count == 1
    assert status.original_heic_count == 1
    assert status.heic_zip_exists is True
    assert status.raw_zip_exists is False
    assert status.edited_zip_exists is False


def test_match_raw_folder_uses_trailing_mmdd_suggestion(make_root_config, touch_file, tmp_path):
    config = make_root_config(tmp_path / "root")
    touch_file(config.raw_folder("10460308") / "x.arw")

    assert match_raw_folder(config, "2026_03_08") == "10460308"


def test_match_raw_folder_prefers_session_map(make_root_config, touch_file, tmp_path):
    config = make_root_config(tmp_path / "root", session_map={"CUSTOM01": "2026_03_08"})
    touch_file(config.raw_folder("CUSTOM01") / "x.arw")
    touch_file(config.raw_folder("10460308") / "x.arw")

    assert match_raw_folder(config, "2026_03_08") == "CUSTOM01"


def test_match_raw_folder_returns_none_without_match(make_root_config, tmp_path):
    config = make_root_config(tmp_path / "root")

    assert match_raw_folder(config, "2026_03_08") is None
