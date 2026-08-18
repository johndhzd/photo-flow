# Photo Flow

macOS-only CLI for backing up a photo library after Capture One exports edited TIFF files. One config points at a single library root that holds many dated sessions.

## Setup

```bash
brew install exiftool imagemagick jpeg-xl p7zip
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp config.example.yaml config.yaml
```

Edit `config.yaml` to point `root_dir` at your library (e.g. `/Volumes/FastData/PhotoEdit`).

## Interactive TUI

Run `photo-flow` with no subcommand to open the terminal UI:

```bash
photo-flow                       # uses ./config.yaml
photo-flow --config config.yaml  # explicit config
photo-flow tui --config config.yaml
```

Pick a session on the left to see its TIFF/processed counts, the matched
`RawPhotos` folder, and which backup zips already exist. Adjust format, quality,
tags, and the overwrite/encrypt/delete toggles, then run any action (Estimate,
Convert, Backup HEIC/RAW/edited, Bundle, Full pipeline) against the selected
session. Progress and command output stream into the log pane. Press `r` to
refresh and `q` to quit. The individual subcommands below remain available for
scripting.

## Library layout

```
<root_dir>/
  RawPhotos/<capture_folder>/     # raw (.ARW) + original HEIF (.HIF) together
  ProcessedPhotos/<YYYY_MM_DD>/   # edited / format-converted output
  TIFF/<YYYY_MM_DD>/              # Capture One TIFF exports
  Backups/                        # archive output
```

A session is identified by a `YYYY_MM_DD` date. The `RawPhotos` capture folder uses a separate naming scheme; the CLI matches it to the date by the trailing `MMDD` digits (e.g. `10460308` -> `2026_03_08`). When the match is ambiguous it asks you to pick or type the folder; confirmed matches can be pinned in `session_map`.

## Commands

Every step runs independently. All commands take `--config` and an optional `--date YYYY_MM_DD` (omitting it shows a picker, unless `--yes`).

```bash
# Estimate converted size for a session's TIFF exports
photo-flow estimate --config config.yaml --date 2026_03_08 --format heic --quality 90

# Convert TIFF/<date> -> ProcessedPhotos/<date>
photo-flow convert --config config.yaml --date 2026_03_08 --format heic --quality 90

# Zip the original HEIF/HIF files -> Backups/<date>/original_heic.zip
photo-flow backup-heic --config config.yaml --date 2026_03_08 --raw 10460308

# Zip the raw files -> Backups/<date>/original_raw.zip
photo-flow backup-raw --config config.yaml --date 2026_03_08 --raw 10460308

# Zip edited files -> Backups/<date>/edited.zip (auto-converts from TIFF if missing)
photo-flow backup-edited --config config.yaml --date 2026_03_08

# Bundle the category zips -> Backups/<date>_<tags>.zip (prompts for tags/encrypt/delete)
photo-flow bundle --config config.yaml --date 2026_03_08

# Full pipeline: heic + raw + edited (+convert) + bundle
photo-flow run --config config.yaml --date 2026_03_08 --tags japan,street
```

### Useful flags

- `--raw <folder>`: override the matched RawPhotos folder.
- `--tags a,b`: tags for the final archive name (otherwise prompted).
- `--encrypt`: produce an encrypted `.7z` bundle (prompts for a password).
- `--delete-intermediate` / `--keep-intermediate`: control removal of the `Backups/<date>` working folder after bundling (otherwise prompted).
- `--overwrite`: re-convert files that already exist in `ProcessedPhotos/<date>`.
- `--yes`: auto-confirm prompts and use the suggested RawPhotos match (requires `--date`).

## Behavior and safety

- Category zips and the final bundle are stored (uncompressed) since photos are already compressed.
- `backup-edited` and `run` auto-convert from `TIFF/<date>` when `ProcessedPhotos/<date>` is empty.
- Sources (`RawPhotos`, `ProcessedPhotos`, `TIFF`) are never deleted. Only the intermediate `Backups/<date>` folder can be removed, after confirmation.
- Conversion verifies each output exists, is non-empty, has metadata, and is a readable image before continuing.

## Config

See `config.example.yaml`.
