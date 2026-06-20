from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from photo_flow.models import RootConfig


SESSION_DATE_RE = re.compile(r"^(\d{4})_(\d{2})_(\d{2})$")

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


class SessionError(RuntimeError):
    pass


def parse_session_date(name: str) -> date:
    match = SESSION_DATE_RE.match(name.strip())
    if not match:
        raise SessionError(f"Session date must look like YYYY_MM_DD, got: {name!r}")
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise SessionError(f"Invalid session date {name!r}: {exc}") from exc


def is_session_date(name: str) -> bool:
    try:
        parse_session_date(name)
    except SessionError:
        return False
    return True


def _list_subdirs(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return [path.name for path in directory.iterdir() if path.is_dir() and not path.name.startswith(".")]


def list_raw_folders(config: RootConfig) -> tuple[str, ...]:
    return tuple(sorted(_list_subdirs(config.raw_photos_dir)))


def list_processed_dates(config: RootConfig) -> tuple[str, ...]:
    return tuple(sorted(name for name in _list_subdirs(config.processed_photos_dir) if is_session_date(name)))


def list_tiff_dates(config: RootConfig) -> tuple[str, ...]:
    return tuple(sorted(name for name in _list_subdirs(config.tiff_dir) if is_session_date(name)))


def available_dates(config: RootConfig) -> tuple[str, ...]:
    return tuple(sorted(set(list_processed_dates(config)) | set(list_tiff_dates(config))))


def suggest_raw_for_date(config: RootConfig, session_date: str) -> str | None:
    """Best-effort match using the trailing MMDD encoded in RawPhotos names.

    RawPhotos folders such as ``10460308`` encode the capture date in their last
    four digits (``0308`` -> March 8). Returns a unique match or ``None`` when
    there is zero or more than one candidate.
    """

    target = parse_session_date(session_date)
    mmdd = f"{target.month:02d}{target.day:02d}"
    candidates = [name for name in list_raw_folders(config) if name.endswith(mmdd)]
    if len(candidates) == 1:
        return candidates[0]
    return None


def date_from_raw_name(config: RootConfig, raw_name: str) -> str | None:
    """Reverse lookup of a session date for a raw folder.

    Uses session_map first, then matches the trailing MMDD against existing
    processed/tiff date folders to infer the year.
    """

    for name, mapped in config.session_map.items():
        if name == raw_name:
            return mapped
    match = re.search(r"(\d{4})$", raw_name)
    if not match:
        return None
    mmdd = match.group(1)
    candidates = [d for d in available_dates(config) if d.replace("_", "")[4:] == mmdd]
    if len(candidates) == 1:
        return candidates[0]
    return None


def select_option(
    options: Sequence[str],
    *,
    prompt: str,
    suggested: str | None,
    input_fn: InputFn,
    output_fn: OutputFn,
    allow_free_text: bool,
) -> str:
    if not options and not allow_free_text:
        raise SessionError("No options available to choose from")
    output_fn(prompt)
    for index, option in enumerate(options, start=1):
        marker = "  <- suggested" if option == suggested else ""
        output_fn(f"  {index}. {option}{marker}")
    hint = "Enter a number"
    if allow_free_text:
        hint += " or type a value"
    if suggested:
        hint += " (blank = suggested)"
    output_fn(hint + ".")

    while True:
        choice = input_fn("> ").strip()
        if not choice:
            if suggested:
                return suggested
            output_fn("No suggestion available; please choose explicitly.")
            continue
        if choice.isdigit():
            position = int(choice)
            if 1 <= position <= len(options):
                return options[position - 1]
            output_fn("Number out of range; try again.")
            continue
        if choice in options or allow_free_text:
            return choice
        output_fn("Unknown value; enter a listed number/name.")


def resolve_session_date(
    config: RootConfig,
    requested: str | None,
    *,
    candidates: Sequence[str],
    assume_yes: bool,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> str:
    if requested:
        parse_session_date(requested)
        return requested
    if assume_yes:
        raise SessionError("No --date provided; pass --date YYYY_MM_DD when using --yes")
    if not candidates:
        raise SessionError("No session dates found under the configured root; pass --date YYYY_MM_DD")
    selection = select_option(
        candidates,
        prompt="Select a session date:",
        suggested=None,
        input_fn=input_fn,
        output_fn=output_fn,
        allow_free_text=True,
    )
    parse_session_date(selection)
    return selection


def resolve_raw_folder(
    config: RootConfig,
    session_date: str,
    requested: str | None,
    *,
    assume_yes: bool,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> str:
    if requested:
        if not config.raw_folder(requested).is_dir():
            raise SessionError(f"RawPhotos folder not found: {config.raw_folder(requested)}")
        return requested

    mapped = next((name for name, value in config.session_map.items() if value == session_date), None)
    if mapped:
        if config.raw_folder(mapped).is_dir():
            return mapped
        output_fn(f"Warning: session_map points {session_date} at missing folder {mapped}")

    suggestion = suggest_raw_for_date(config, session_date)
    folders = list_raw_folders(config)
    if not folders:
        raise SessionError(f"No RawPhotos folders found under {config.raw_photos_dir}")

    if assume_yes:
        if suggestion:
            return suggestion
        raise SessionError(
            f"Could not unambiguously match {session_date} to a RawPhotos folder; "
            "pass --raw <folder> when using --yes"
        )

    selection = select_option(
        folders,
        prompt=f"Select the RawPhotos folder for session {session_date}:",
        suggested=suggestion,
        input_fn=input_fn,
        output_fn=output_fn,
        allow_free_text=False,
    )
    if not config.raw_folder(selection).is_dir():
        raise SessionError(f"RawPhotos folder not found: {config.raw_folder(selection)}")
    return selection
