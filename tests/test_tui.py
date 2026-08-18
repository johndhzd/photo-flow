import asyncio
import zipfile

import yaml
from textual.widgets import ListView

from _helpers import build_root_config, touch
from photo_flow import cli
from photo_flow.tui import PhotoFlowApp


def _build_config(tmp_path):
    root = tmp_path / "PhotoEdit"
    config = build_root_config(root)
    touch(config.tiff_dir_for("2026_03_08") / "DSC0001.tif")
    (config.processed_photos_dir / "2026_02_01").mkdir(parents=True)
    touch(config.raw_folder("10460308") / "DSC0001.HIF")
    return config


def test_tui_lists_sessions_newest_first_and_selects_first(tmp_path):
    config = _build_config(tmp_path)

    async def scenario():
        app = PhotoFlowApp(config, tmp_path / "config.yaml")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            names = [item.name for item in app.query_one("#sessions", ListView).children]
            assert names == ["2026_03_08", "2026_02_01"]
            assert app._selected_date == "2026_03_08"

    asyncio.run(scenario())


def test_tui_backup_heic_action_creates_zip(tmp_path):
    config = _build_config(tmp_path)

    async def scenario():
        app = PhotoFlowApp(config, tmp_path / "config.yaml")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app._run_action("backup-heic")
            await app.workers.wait_for_complete()
            await pilot.pause()

    asyncio.run(scenario())

    zip_path = config.backup_work_dir("2026_03_08") / "original_heic.zip"
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.namelist() == ["DSC0001.HIF"]


def test_main_without_subcommand_launches_tui(tmp_path, monkeypatch):
    root = tmp_path / "PhotoEdit"
    root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"root_dir": str(root)}), encoding="utf-8")

    calls: dict[str, object] = {}

    def fake_run_tui(config, path):
        calls["config"] = config
        calls["path"] = path
        return 0

    monkeypatch.setattr("photo_flow.tui.run_tui", fake_run_tui)

    assert cli.main(["--config", str(config_path)]) == 0
    assert calls["path"] == config_path
    assert calls["config"].root_dir == root
