from datetime import datetime
from pathlib import Path

from photo_flow.logging_setup import log_path_for_run
from photo_flow.models import CommandResult
from photo_flow.trash import build_trash_command, trash_files


def test_build_trash_command_passes_all_paths():
    assert build_trash_command((Path("a.tif"), Path("b.tif"))) == ("trash", "a.tif", "b.tif")


def test_trash_files_uses_runner():
    calls = []

    def runner(args):
        calls.append(tuple(args))
        return CommandResult(tuple(args), 0, "", "")

    result = trash_files((Path("a.tif"), Path("b.tif")), runner=runner)

    assert calls == [("trash", "a.tif", "b.tif")]
    assert result.ok is True


def test_log_path_for_run_uses_timestamp(tmp_path):
    path = log_path_for_run(tmp_path, datetime(2026, 6, 10, 12, 30, 5))

    assert path == tmp_path / "photo-flow-20260610-123005.log"
