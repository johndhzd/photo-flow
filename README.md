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

Edit `config.yaml` for one photo session, then run:

```bash
photo-flow estimate --config config.yaml
photo-flow run --config config.yaml
```

## Safety

- RAW files are never deleted.
- TIFF cleanup moves files to macOS Trash after confirmation.
- Missing backup destinations warn and continue.
- Conversion or integrity failures stop cleanup and backup by default.
