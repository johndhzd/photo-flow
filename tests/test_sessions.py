import pytest

from _helpers import build_root_config

from photo_flow.sessions import (
    SessionError,
    available_dates,
    date_from_raw_name,
    is_session_date,
    list_raw_folders,
    parse_session_date,
    resolve_raw_folder,
    resolve_session_date,
    suggest_raw_for_date,
)


def make_tree(tmp_path, raw_names=(), processed=(), tiff=(), session_map=None):
    config = build_root_config(tmp_path, session_map=session_map or {})
    for name in raw_names:
        config.raw_folder(name).mkdir(parents=True, exist_ok=True)
    for name in processed:
        config.processed_dir_for(name).mkdir(parents=True, exist_ok=True)
    for name in tiff:
        config.tiff_dir_for(name).mkdir(parents=True, exist_ok=True)
    return config


def test_parse_and_is_session_date():
    assert parse_session_date("2026_03_08").isoformat() == "2026-03-08"
    assert is_session_date("2026_03_08") is True
    assert is_session_date("RawPhotos") is False
    with pytest.raises(SessionError):
        parse_session_date("2026-03-08")


def test_list_raw_folders_ignores_dotfiles(tmp_path):
    config = make_tree(tmp_path, raw_names=("10460308", "10760418"))
    (config.raw_photos_dir / ".DS_Store").write_bytes(b"x")
    assert list_raw_folders(config) == ("10460308", "10760418")


def test_suggest_raw_for_date_matches_trailing_mmdd(tmp_path):
    config = make_tree(tmp_path, raw_names=("10460308", "10760418"))
    assert suggest_raw_for_date(config, "2026_03_08") == "10460308"
    assert suggest_raw_for_date(config, "2026_04_18") == "10760418"
    assert suggest_raw_for_date(config, "2026_12_31") is None


def test_suggest_raw_for_date_ambiguous_returns_none(tmp_path):
    config = make_tree(tmp_path, raw_names=("10460308", "99990308"))
    assert suggest_raw_for_date(config, "2026_03_08") is None


def test_available_dates_unions_processed_and_tiff(tmp_path):
    config = make_tree(tmp_path, processed=("2026_03_08",), tiff=("2026_03_08", "2026_04_18"))
    assert available_dates(config) == ("2026_03_08", "2026_04_18")


def test_date_from_raw_name_uses_session_map_then_heuristic(tmp_path):
    config = make_tree(
        tmp_path,
        raw_names=("10460308",),
        processed=("2026_03_08",),
        session_map={"weird_name": "2026_05_24"},
    )
    assert date_from_raw_name(config, "weird_name") == "2026_05_24"
    assert date_from_raw_name(config, "10460308") == "2026_03_08"


def test_resolve_session_date_returns_requested_without_prompt(tmp_path):
    config = make_tree(tmp_path)
    result = resolve_session_date(
        config,
        "2026_03_08",
        candidates=(),
        assume_yes=False,
        input_fn=_no_input,
        output_fn=_sink,
    )
    assert result == "2026_03_08"


def test_resolve_session_date_yes_without_date_errors(tmp_path):
    config = make_tree(tmp_path)
    with pytest.raises(SessionError, match="No --date"):
        resolve_session_date(
            config,
            None,
            candidates=("2026_03_08",),
            assume_yes=True,
            input_fn=_no_input,
            output_fn=_sink,
        )


def test_resolve_session_date_interactive_select_by_number(tmp_path):
    config = make_tree(tmp_path)
    result = resolve_session_date(
        config,
        None,
        candidates=("2026_03_08", "2026_04_18"),
        assume_yes=False,
        input_fn=_scripted(["2"]),
        output_fn=_sink,
    )
    assert result == "2026_04_18"


def test_resolve_raw_folder_uses_override(tmp_path):
    config = make_tree(tmp_path, raw_names=("10460308",))
    result = resolve_raw_folder(
        config,
        "2026_03_08",
        "10460308",
        assume_yes=False,
        input_fn=_no_input,
        output_fn=_sink,
    )
    assert result == "10460308"


def test_resolve_raw_folder_override_missing_errors(tmp_path):
    config = make_tree(tmp_path, raw_names=("10460308",))
    with pytest.raises(SessionError, match="RawPhotos folder not found"):
        resolve_raw_folder(
            config,
            "2026_03_08",
            "missing",
            assume_yes=False,
            input_fn=_no_input,
            output_fn=_sink,
        )


def test_resolve_raw_folder_yes_uses_suggestion(tmp_path):
    config = make_tree(tmp_path, raw_names=("10460308", "10760418"))
    result = resolve_raw_folder(
        config,
        "2026_03_08",
        None,
        assume_yes=True,
        input_fn=_no_input,
        output_fn=_sink,
    )
    assert result == "10460308"


def test_resolve_raw_folder_yes_ambiguous_errors(tmp_path):
    config = make_tree(tmp_path, raw_names=("10460308", "99990308"))
    with pytest.raises(SessionError, match="Could not unambiguously match"):
        resolve_raw_folder(
            config,
            "2026_03_08",
            None,
            assume_yes=True,
            input_fn=_no_input,
            output_fn=_sink,
        )


def test_resolve_raw_folder_interactive_blank_accepts_suggestion(tmp_path):
    config = make_tree(tmp_path, raw_names=("10460308", "10760418"))
    result = resolve_raw_folder(
        config,
        "2026_03_08",
        None,
        assume_yes=False,
        input_fn=_scripted([""]),
        output_fn=_sink,
    )
    assert result == "10460308"


def test_resolve_raw_folder_session_map_takes_priority(tmp_path):
    config = make_tree(
        tmp_path,
        raw_names=("10460308", "weird"),
        session_map={"weird": "2026_03_08"},
    )
    result = resolve_raw_folder(
        config,
        "2026_03_08",
        None,
        assume_yes=True,
        input_fn=_no_input,
        output_fn=_sink,
    )
    assert result == "weird"


def _sink(_message):
    return None


def _no_input(_prompt):
    raise AssertionError("input should not be requested")


def _scripted(responses):
    queue = list(responses)

    def _fn(_prompt):
        return queue.pop(0)

    return _fn
