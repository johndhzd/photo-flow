from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    RichLog,
    Select,
    Static,
)

from photo_flow.estimator import EstimateResult, format_bytes
from photo_flow.logging_setup import log_path_for_run
from photo_flow.models import OutputFormat, RootConfig
from photo_flow.parallel import default_workers
from photo_flow.session_status import SessionStatus, build_session_status, match_raw_folder
from photo_flow.sessions import available_dates, list_raw_folders

# Which actions need which extra inputs, so the app can resolve them before
# kicking off the (blocking) worker.
_RAW_ACTIONS = {"backup-heic", "backup-raw", "run"}
_ENCRYPT_ACTIONS = {"bundle", "run"}

_ACTION_LABELS: tuple[tuple[str, str], ...] = (
    ("estimate", "Estimate"),
    ("convert", "Convert"),
    ("backup-heic", "Backup HEIC"),
    ("backup-raw", "Backup RAW"),
    ("backup-edited", "Backup edited"),
    ("bundle", "Bundle"),
    ("run", "Full pipeline"),
)


@dataclass(frozen=True)
class JobSettings:
    output_format: OutputFormat
    quality: int
    overwrite: bool
    tags: tuple[str, ...]
    encrypt: bool
    delete_intermediate: bool


class RawFolderModal(ModalScreen[str | None]):
    """Pick a RawPhotos folder when the automatic match is ambiguous."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, folders: tuple[str, ...], session_date: str) -> None:
        super().__init__()
        self._folders = folders
        self._session_date = session_date

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(f"Select the RawPhotos folder for {self._session_date}:")
            yield ListView(
                *(ListItem(Label(name), name=name) for name in self._folders),
                id="raw-folders",
            )
            yield Button("Cancel", id="raw-cancel")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class PasswordModal(ModalScreen[str | None]):
    """Collect and confirm a backup password for encrypted bundles."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label("Backup password for the encrypted archive:")
            yield Input(password=True, placeholder="Password", id="pw1")
            yield Input(password=True, placeholder="Confirm password", id="pw2")
            yield Static("", id="pw-error")
            with Horizontal(id="modal-buttons"):
                yield Button("OK", variant="primary", id="pw-ok")
                yield Button("Cancel", id="pw-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pw-cancel":
            self.dismiss(None)
            return
        first = self.query_one("#pw1", Input).value
        second = self.query_one("#pw2", Input).value
        error = self.query_one("#pw-error", Static)
        if not first:
            error.update("Password cannot be empty.")
            return
        if first != second:
            error.update("Passwords do not match.")
            return
        self.dismiss(first)

    def action_cancel(self) -> None:
        self.dismiss(None)


class PhotoFlowApp(App[int]):
    TITLE = "Photo Flow"

    CSS = """
    #body {
        height: 1fr;
    }
    #sidebar {
        width: 32;
        border-right: solid $panel;
    }
    #sidebar Label.heading {
        padding: 0 1;
        text-style: bold;
    }
    #sessions {
        height: 1fr;
    }
    #main {
        width: 1fr;
    }
    #status {
        height: auto;
        padding: 1;
        border-bottom: solid $panel;
    }
    #settings {
        height: auto;
        padding: 0 1;
    }
    #settings .row {
        height: auto;
        padding: 0 0;
    }
    #settings Label {
        width: 12;
        content-align: left middle;
    }
    #settings Input {
        width: 18;
    }
    #settings Select {
        width: 18;
    }
    #actions {
        height: auto;
        padding: 1;
    }
    #actions Button {
        margin: 0 1 0 0;
    }
    #log {
        height: 1fr;
        border-top: solid $panel;
    }
    #progress-row {
        height: auto;
        padding: 0 1;
    }
    #progress-label {
        width: 30;
        content-align: left middle;
    }
    ModalScreen {
        align: center middle;
    }
    #modal {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $panel;
        border: thick $primary;
    }
    #modal ListView {
        height: auto;
        max-height: 12;
    }
    #modal-buttons {
        height: auto;
        padding-top: 1;
    }
    #pw-error {
        color: $error;
        height: auto;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, config: RootConfig, config_path: Path) -> None:
        super().__init__()
        self._config = config
        self._config_path = config_path
        self._worker_count = default_workers()
        self._selected_date: str | None = None
        self.sub_title = str(config_path)

    # --------------------------------------------------------------------- #
    # Composition
    # --------------------------------------------------------------------- #

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Label("Sessions", classes="heading")
                yield ListView(id="sessions")
            with Vertical(id="main"):
                yield Static("Select a session.", id="status")
                with VerticalScroll(id="settings"):
                    with Horizontal(classes="row"):
                        yield Label("Format")
                        yield Select(
                            [(fmt.value.upper(), fmt.value) for fmt in OutputFormat],
                            value=self._config.default_format.value,
                            allow_blank=False,
                            id="format",
                        )
                    with Horizontal(classes="row"):
                        yield Label("Quality")
                        yield Input(
                            value=str(self._config.default_quality),
                            type="integer",
                            id="quality",
                        )
                    with Horizontal(classes="row"):
                        yield Label("Tags")
                        yield Input(placeholder="japan,street", id="tags")
                    with Horizontal(classes="row"):
                        yield Checkbox(
                            "Overwrite",
                            value=self._config.overwrite_existing,
                            id="overwrite",
                        )
                        yield Checkbox("Encrypt", id="encrypt")
                        yield Checkbox("Delete intermediate", id="delete")
                with Horizontal(id="actions"):
                    for action, label in _ACTION_LABELS:
                        yield Button(label, id=f"act-{action}")
                with Horizontal(id="progress-row"):
                    yield Static("", id="progress-label")
                    yield ProgressBar(id="progress", show_eta=False)
                yield RichLog(id="log", highlight=False, markup=False, wrap=True)
        yield Footer()

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #

    def on_mount(self) -> None:
        self._configure_logging()
        self.begin_capture_print(self)
        self._load_sessions()
        self._log(f"Loaded config: {self._config_path}")
        self._log(f"Root: {self._config.root_dir}")

    def _configure_logging(self) -> None:
        # File-only logging so do_* logging calls never draw on the TUI surface.
        timestamp = datetime.now(timezone.utc)
        self._config.log_dir.mkdir(parents=True, exist_ok=True)
        path = log_path_for_run(self._config.log_dir, timestamp)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[logging.FileHandler(path, encoding="utf-8")],
            force=True,
        )

    def _load_sessions(self) -> None:
        dates = tuple(reversed(available_dates(self._config)))  # newest first
        sessions = self.query_one("#sessions", ListView)
        sessions.clear()
        for date in dates:
            sessions.append(ListItem(Label(date), name=date))
        if dates:
            sessions.index = 0
            self._selected_date = dates[0]
        else:
            self._selected_date = None
            self._log("No sessions found under the configured root.")
        self._refresh_detail()

    # --------------------------------------------------------------------- #
    # Selection + detail panel
    # --------------------------------------------------------------------- #

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "sessions":
            return
        self._selected_date = event.item.name if event.item else None
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        status_widget = self.query_one("#status", Static)
        if self._selected_date is None:
            status_widget.update("Select a session.")
            return
        status = build_session_status(self._config, self._selected_date)
        status_widget.update(_render_status(status))

    def action_refresh(self) -> None:
        self._load_sessions()
        self._refresh_detail()
        self._log("Refreshed.")

    # --------------------------------------------------------------------- #
    # Actions
    # --------------------------------------------------------------------- #

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("act-"):
            self._run_action(button_id.removeprefix("act-"))

    @work(exclusive=True, group="action")
    async def _run_action(self, action: str) -> None:
        if self._selected_date is None:
            self._log("[error] Select a session first.")
            return
        date = self._selected_date

        try:
            settings = self._read_settings()
        except ValueError as exc:
            self._log(f"[error] {exc}")
            return

        raw_name: str | None = None
        if action in _RAW_ACTIONS:
            raw_name = match_raw_folder(self._config, date)
            if raw_name is None:
                folders = list_raw_folders(self._config)
                if not folders:
                    self._log("[error] No RawPhotos folders found under the configured root.")
                    return
                raw_name = await self.push_screen_wait(RawFolderModal(folders, date))
                if not raw_name:
                    self._log("Cancelled.")
                    return

        password: str | None = None
        if settings.encrypt and action in _ENCRYPT_ACTIONS:
            password = await self.push_screen_wait(PasswordModal())
            if password is None:
                self._log("Cancelled.")
                return

        self._set_running(True)
        self._log(f"--- {action} :: {date} ---")
        try:
            await asyncio.to_thread(
                self._execute, action, date, settings, raw_name, password
            )
            self._log(f"[done] {action}")
        except Exception as exc:  # noqa: BLE001 - surface any tool/IO failure in the log
            self._log(f"[error] {exc}")
        finally:
            self._reset_progress()
            self._set_running(False)
            self._refresh_detail()

    def _execute(
        self,
        action: str,
        date: str,
        settings: JobSettings,
        raw_name: str | None,
        password: str | None,
    ) -> None:
        # Imported lazily to avoid a module-load cycle (cli imports tui on launch).
        from photo_flow import cli
        from photo_flow.progress import progress_sink

        def sink(current: int, total: int, desc: str) -> None:
            self.call_from_thread(self._update_progress, current, total, desc)

        with progress_sink(sink):
            if action == "estimate":
                result = cli.do_estimate(
                    self._config,
                    date,
                    settings.output_format,
                    settings.quality,
                    workers=self._worker_count,
                )
                if result is None:
                    print(f"No TIFF files found in {self._config.tiff_dir_for(date)}.")
                else:
                    print(_render_estimate(date, settings, result))
            elif action == "convert":
                cli.do_convert(
                    self._config,
                    date,
                    settings.output_format,
                    settings.quality,
                    overwrite=settings.overwrite,
                    workers=self._worker_count,
                )
            elif action == "backup-heic":
                assert raw_name is not None
                cli.do_backup_heic(self._config, date, raw_name)
            elif action == "backup-raw":
                assert raw_name is not None
                cli.do_backup_raw(self._config, date, raw_name)
            elif action == "backup-edited":
                cli.do_backup_edited(
                    self._config,
                    date,
                    settings.output_format,
                    settings.quality,
                    overwrite=settings.overwrite,
                    workers=self._worker_count,
                )
            elif action == "bundle":
                cli.do_bundle(
                    self._config,
                    date,
                    tags=settings.tags,
                    encrypt=settings.encrypt,
                    delete_intermediate=settings.delete_intermediate,
                    password=password,
                )
            elif action == "run":
                assert raw_name is not None
                cli.do_backup_heic(self._config, date, raw_name)
                cli.do_backup_raw(self._config, date, raw_name)
                cli.do_backup_edited(
                    self._config,
                    date,
                    settings.output_format,
                    settings.quality,
                    overwrite=settings.overwrite,
                    workers=self._worker_count,
                )
                cli.do_bundle(
                    self._config,
                    date,
                    tags=settings.tags,
                    encrypt=settings.encrypt,
                    delete_intermediate=settings.delete_intermediate,
                    password=password,
                )

    # --------------------------------------------------------------------- #
    # Settings + helpers
    # --------------------------------------------------------------------- #

    def _read_settings(self) -> JobSettings:
        raw_quality = self.query_one("#quality", Input).value.strip()
        try:
            quality = int(raw_quality)
        except ValueError as exc:
            raise ValueError("Quality must be a whole number between 1 and 100.") from exc
        if not 1 <= quality <= 100:
            raise ValueError("Quality must be between 1 and 100.")
        output_format = OutputFormat.parse(str(self.query_one("#format", Select).value))
        tags_raw = self.query_one("#tags", Input).value
        tags = tuple(tag.strip() for tag in tags_raw.split(",") if tag.strip())
        return JobSettings(
            output_format=output_format,
            quality=quality,
            overwrite=self.query_one("#overwrite", Checkbox).value,
            tags=tags,
            encrypt=self.query_one("#encrypt", Checkbox).value,
            delete_intermediate=self.query_one("#delete", Checkbox).value,
        )

    def _set_running(self, running: bool) -> None:
        self.query_one("#actions").disabled = running

    def _update_progress(self, current: int, total: int, desc: str) -> None:
        bar = self.query_one("#progress", ProgressBar)
        bar.update(total=total, progress=current)
        self.query_one("#progress-label", Static).update(f"{desc} {current}/{total}")

    def _reset_progress(self) -> None:
        bar = self.query_one("#progress", ProgressBar)
        bar.update(total=None, progress=0)
        self.query_one("#progress-label", Static).update("")

    def _log(self, message: str) -> None:
        self.query_one("#log", RichLog).write(message)

    # --------------------------------------------------------------------- #
    # Captured stdout from do_* helpers
    # --------------------------------------------------------------------- #

    def on_print(self, event: events.Print) -> None:
        text = event.text.rstrip("\n")
        if text.strip():
            self._log(text)


def _render_status(status: SessionStatus) -> str:
    raw = status.raw_name or "(unmatched)"
    zips = []
    zips.append(("original_heic.zip", status.heic_zip_exists))
    zips.append(("original_raw.zip", status.raw_zip_exists))
    zips.append(("edited.zip", status.edited_zip_exists))
    zip_line = "  ".join(f"{'[x]' if present else '[ ]'} {name}" for name, present in zips)
    return (
        f"Session {status.session_date}\n"
        f"TIFF exports:    {status.tiff_count}\n"
        f"Processed files: {status.processed_count}\n"
        f"RawPhotos:       {raw} "
        f"(raw {status.raw_count}, original heic {status.original_heic_count})\n"
        f"Backups:         {zip_line}"
    )


def _render_estimate(date: str, settings: JobSettings, result: EstimateResult) -> str:
    return (
        f"Estimate for {date} ({settings.output_format.value}, q{settings.quality})\n"
        f"  Sample files: {result.sample_count}\n"
        f"  Sample input: {format_bytes(result.sample_input_bytes)}\n"
        f"  Sample output: {format_bytes(result.sample_output_bytes)}\n"
        f"  Estimated total output: {format_bytes(result.estimated_output_bytes)}"
    )


def run_tui(config: RootConfig, config_path: Path) -> int:
    app = PhotoFlowApp(config, config_path)
    result = app.run()
    return result if isinstance(result, int) else 0
