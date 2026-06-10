# Photo Flow

macOS-only CLI for automating a photo workflow after Capture One exports edited TIFF files.

## Setup

```bash
brew install exiftool imagemagick jpeg-xl p7zip trash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp config.example.yaml config.yaml
```

Edit `config.yaml` for one photo session.

## Estimate Output Size

```bash
photo-flow estimate --config config.yaml --format heic --quality 90
photo-flow estimate --config config.yaml --format jxl --quality 85
```

The estimate converts a small sample to temporary files and extrapolates total output size. It is intended for format and quality comparison, not exact prediction.

## Run Workflow

```bash
photo-flow run --config config.yaml --format heic --quality 90 --tags japan,street
photo-flow run --config config.yaml --format jxl --quality 85 --tags private --encrypt
```

The command:

1. Converts TIFF exports into the configured converted output folder.
2. Copies metadata from TIFFs to converted outputs.
3. Verifies converted files exist, are non-empty, readable, and have metadata.
4. Asks before moving TIFF files to macOS Trash.
5. Backs up remaining RAW files, original HEIC files, converted outputs, manifest, and log.
6. Copies the archive to every existing configured backup destination.

## Safety

- RAW files are never deleted.
- TIFF cleanup moves files to macOS Trash after confirmation.
- Missing backup destinations warn and continue.
- Conversion or integrity failures stop cleanup and backup by default.
- Existing converted files are not overwritten unless `--overwrite` is passed or `overwrite_existing: true` is set.

## Config

See `config.example.yaml`.
