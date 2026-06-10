# Photo Workflow Automation Design

## Goal

Build a macOS-only Python CLI that automates the post-edit photo workflow after Capture One exports edited TIFF files. The tool converts TIFF files to a chosen delivery format, verifies the converted files, optionally trashes TIFF sources, and creates backups of the remaining selected RAW files, original HEIC files, and converted outputs.

## User Workflow

The tool processes one photo session per run. Before running it, the user has already deleted unwanted RAW files, so every RAW file remaining in the configured RAW folder is treated as selected and must be backed up.

The main command will be:

```bash
photo-flow run --config config.yaml
```

Optional runtime overrides include output format, quality, tags, encryption choice, and overwrite behavior:

```bash
photo-flow run --config config.yaml --format heic --quality 90 --tags japan,street
photo-flow estimate --config config.yaml --format jxl --quality 85
```

The run flow is:

1. Load and validate the YAML config.
2. Check required Homebrew/macOS command-line dependencies.
3. Scan the configured RAW, original HEIC, TIFF, and converted output folders.
4. Estimate converted output size from a small sample of TIFF files.
5. Show the estimate and ask for confirmation before conversion.
6. Convert all TIFF files into the configured converted output folder.
7. Copy metadata from each TIFF into its converted output where the target format supports it.
8. Verify every converted file exists, is non-empty, can be identified as an image, and has expected metadata.
9. If verification succeeds, ask before moving TIFF files to macOS Trash.
10. Create a backup archive containing selected RAW files, original HEIC files, converted files, a manifest, and the run log.
11. Copy the backup archive to every configured backup destination that exists.
12. Warn and continue when a backup destination is missing.
13. Log all operations, confirmations, warnings, errors, backup paths, and trashed files.

The tool does not import files into the macOS Photos library. The user imports converted files manually.

## Configuration

The project will include an example YAML config:

```yaml
raw_dir: /path/to/session/raw
original_heic_dir: /path/to/session/original_heic
tiff_dir: /path/to/session/tiff_exports
converted_output_dir: /path/to/session/converted
log_dir: /path/to/photo-flow/logs

default_format: heic
default_quality: 90
overwrite_existing: false

raw_extensions:
  - .arw
  - .cr3
  - .nef
  - .raf
  - .rw2
  - .dng

backup_destinations:
  - /Volumes/BackupDrive/PhotoBackups
  - /Volumes/NAS/PhotoBackups
```

Output format can be one of:

- `heic`
- `jpg`
- `png`
- `jxl`

The config is the default source of truth. Command-line options override config values for a single run.

## File Matching

Files are matched by exact basename with no suffix rules.

Example:

```text
TIFF export:    DSC01234.tif
Converted file: DSC01234.heic
Original HEIC:  DSC01234.heic
RAW file:       DSC01234.ARW
```

The scanner will not infer edited RAW selection from TIFF files. It backs up every RAW file currently present in the configured RAW folder.

Existing converted files are handled conservatively. By default, the tool refuses to overwrite an existing converted output file. The user can opt in with `--overwrite`.

## Architecture

The implementation will be a Python package with focused modules:

- `photo_flow/cli.py`: command-line interface, runtime overrides, interactive confirmations.
- `photo_flow/config.py`: YAML config loading, defaults, and validation.
- `photo_flow/dependencies.py`: checks for required external tools.
- `photo_flow/scanner.py`: scans one session and builds a structured file inventory.
- `photo_flow/converter.py`: converts TIFF files to the requested format and quality.
- `photo_flow/metadata.py`: copies and verifies metadata with `exiftool`.
- `photo_flow/estimator.py`: creates small sample conversions and extrapolates output size.
- `photo_flow/integrity.py`: verifies converted outputs are present, readable, and non-empty.
- `photo_flow/backup.py`: creates `.zip` or encrypted `.7z` archives and copies them to destinations.
- `photo_flow/trash.py`: moves TIFF files to macOS Trash after confirmation.
- `photo_flow/logging_setup.py`: creates readable timestamped logs.
- `tests/`: unit tests for config validation, scanning, estimation math, command construction, backup destination behavior, and safety prompts.

The CLI should keep shell execution behind small helper functions so tests can verify command construction without requiring real photos or external tools.

## External Tools

Homebrew dependencies are allowed. The implementation should validate dependencies before doing destructive or expensive work.

Expected tools:

- `exiftool`: metadata copy and metadata verification.
- `magick`: conversion and image identification for HEIC/JPEG/PNG where supported.
- `libheif` tools or ImageMagick HEIC support: HEIC output support.
- `jpeg-xl`: `cjxl` for JPEG XL output.
- `p7zip`: encrypted `.7z` archive creation.
- `trash`: move files to macOS Trash from the CLI.

Python package dependencies should be minimal:

- `click` or `argparse` for the CLI.
- `PyYAML` for config parsing.
- `pytest` for tests.

## Conversion

The converter writes files into the configured converted output folder, never next to the TIFF sources unless the config explicitly points there.

Quality handling:

- `heic`, `jpg`, and `jxl` use a numeric quality setting.
- `png` ignores lossy quality and should warn that PNG output is lossless.

The exact command flags may vary by installed tool support, so command construction should be isolated per format. The implementation plan should include a small adapter per format instead of spreading format-specific shell flags through the CLI.

## Size Estimation

The `estimate` flow converts a small sample of TIFF files into a temporary directory and extrapolates total output size.

Sampling rules:

- Use up to five TIFF files.
- Prefer a spread across the file list rather than only the first files.
- Show the sample count, sample input size, sample output size, estimated total output size, requested format, and requested quality.
- Label the result clearly as an estimate.

Temporary sample outputs are deleted after estimation.

## Integrity Checks

After conversion, every expected converted file must pass these checks:

- File exists.
- File size is greater than zero.
- Image identification succeeds through the selected tool.
- Metadata copy command succeeded.
- Basic metadata can be read back with `exiftool`.

If any converted file is missing or appears corrupted, the tool logs the error and stops before TIFF cleanup and backup by default. The CLI may offer an explicit continue prompt, but the default is to stop.

## Cleanup

The tool never deletes RAW files.

TIFF cleanup means moving files to macOS Trash, not permanent deletion. TIFF cleanup is only offered after conversion and integrity verification succeed. The user must explicitly confirm before any TIFF file is moved.

The log records every trashed TIFF path and whether the Trash operation succeeded.

## Backup

Backups include:

- All RAW files currently in the configured RAW folder.
- All original HEIC files in the configured original HEIC folder.
- All converted output files for the run.
- A manifest file.
- The run log.

Unencrypted backups use `.zip`. Encrypted backups use `.7z` with AES-256 encryption through `p7zip`.

At runtime, the tool asks whether to encrypt the backup. If encryption is enabled, it prompts for a password without echoing it and confirms the password before archive creation.

Archive names use the current date and user-provided tags:

```text
YYYY-MM-DD_tag1_tag2.zip
YYYY-MM-DD_tag1_tag2.7z
```

The backup destination config is a list. For each destination:

- If it exists, copy the archive there and log the resulting path.
- If it does not exist, warn the user, log the warning, and continue to the next destination.

## Manifest

Every backup includes a manifest with:

- Run timestamp.
- Output format and quality.
- Source directories.
- Converted output directory.
- Backup destinations.
- Tool versions.
- Included file list.
- SHA-256 hash for each included file.
- Conversion warnings and verification results.

The manifest makes the backup auditable and helps diagnose corrupted or missing files later.

## Error Handling

The CLI should fail early for:

- Invalid config syntax.
- Missing required source directories.
- Unsupported output format.
- Missing conversion dependencies for the requested format.
- Existing output files when overwrite is disabled.

The CLI should warn and continue for:

- Missing backup destinations.
- PNG quality being ignored.

The CLI should stop before cleanup and backup for:

- Conversion failures.
- Missing converted files.
- Corrupted or unreadable converted files.
- Metadata copy or verification failures.

## Testing Strategy

The implementation should use test-driven development for behavior that can be tested without real photos:

- Config loading, defaults, and validation.
- File scanning and exact basename matching.
- Output path planning.
- Existing-output overwrite protection.
- Estimation extrapolation math.
- Backup destination handling when some destinations are missing.
- Archive name generation from date and tags.
- Shell command construction for each output format.
- Safety behavior that prevents cleanup after failed verification.

Integration tests with real image tools can be optional and marked separately because they require Homebrew dependencies and fixture images.

## Out Of Scope

The first version will not:

- Import converted files into macOS Photos.
- Delete RAW files.
- Infer selected RAW files from TIFF exports.
- Provide a GUI.
- Support Windows or Linux.
- Guarantee exact output size prediction.
