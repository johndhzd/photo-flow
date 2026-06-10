# Photo Workflow Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS-only Python CLI named `photo-flow` that automates TIFF conversion, integrity checks, optional TIFF trash cleanup, and multi-destination backups for one photo session per run.

**Architecture:** The project is a small Python package with a thin `argparse` CLI and focused modules for config, scanning, conversion command planning, estimation, metadata, integrity, backup, trash, and logging. Homebrew tools are invoked behind command/executor boundaries so most behavior is unit-testable without real photos.

**Tech Stack:** Python 3.11+, `argparse`, `PyYAML`, `pytest`, Homebrew tools `exiftool`, `magick`, `cjxl`, `7z`, and `trash`.

---

## File Structure

- Create: `pyproject.toml` - package metadata, console script, dependencies, pytest config.
- Create: `.gitignore` - ignore Python caches, virtualenvs, logs, temp output, local configs.
- Create: `README.md` - concise setup and run instructions.
- Create: `config.example.yaml` - sample config for one photo session.
- Create: `photo_flow/__init__.py` - package version.
- Create: `photo_flow/__main__.py` - supports `python -m photo_flow`.
- Create: `photo_flow/models.py` - dataclasses and enums shared across modules.
- Create: `photo_flow/config.py` - YAML loading, defaults, validation.
- Create: `photo_flow/scanner.py` - session inventory and exact basename scanning.
- Create: `photo_flow/commands.py` - shell command runner abstraction.
- Create: `photo_flow/converter.py` - output paths and conversion command construction/execution.
- Create: `photo_flow/estimator.py` - sample selection and size extrapolation.
- Create: `photo_flow/dependencies.py` - external tool dependency planning.
- Create: `photo_flow/metadata.py` - `exiftool` metadata copy and verification.
- Create: `photo_flow/integrity.py` - converted output checks.
- Create: `photo_flow/backup.py` - manifest, archive naming, archive creation, destination copy.
- Create: `photo_flow/trash.py` - macOS Trash command wrapper.
- Create: `photo_flow/logging_setup.py` - timestamped log file setup.
- Create: `photo_flow/cli.py` - `run` and `estimate` commands with confirmations.
- Create: `tests/conftest.py` - shared fixtures.
- Create: test files next to the behavior they validate.

---

## Task 1: Initialize Project Metadata

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `config.example.yaml`
- Modify: `docs/superpowers/specs/2026-06-10-photo-workflow-automation-design.md`

- [ ] **Step 1: Initialize git repository**

Run:

```bash
git init
```

Expected: `Initialized empty Git repository` or `Reinitialized existing Git repository`.

- [ ] **Step 2: Create project metadata files**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "photo-flow"
version = "0.1.0"
description = "macOS photo workflow automation for TIFF conversion and backups"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "PyYAML>=6.0.1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
]

[project.scripts]
photo-flow = "photo_flow.cli:main"

[tool.setuptools.packages.find]
include = ["photo_flow*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

Create `.gitignore`:

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/
dist/
build/
*.egg-info/

*.log
logs/
tmp/
.DS_Store
config.yaml
```

Create `README.md`:

```markdown
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
```

Create `config.example.yaml`:

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

- [ ] **Step 3: Run metadata sanity checks**

Run:

```bash
python3 - <<'PY'
import tomllib
from pathlib import Path
tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
for path in ["README.md", "config.example.yaml"]:
    assert Path(path).exists(), path
print("metadata files present")
PY
```

Expected: `metadata files present`.

- [ ] **Step 4: Commit**

```bash
git add .gitignore README.md config.example.yaml pyproject.toml docs/superpowers/specs/2026-06-10-photo-workflow-automation-design.md
git commit -m "chore: initialize photo-flow project"
```

---

## Task 2: Add Shared Models

**Files:**
- Create: `photo_flow/__init__.py`
- Create: `photo_flow/__main__.py`
- Create: `photo_flow/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_models.py`:

```python
from pathlib import Path

import pytest

from photo_flow.models import OutputFormat, format_extension


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("heic", OutputFormat.HEIC),
        ("jpg", OutputFormat.JPG),
        ("jpeg", OutputFormat.JPG),
        ("png", OutputFormat.PNG),
        ("jxl", OutputFormat.JXL),
    ],
)
def test_output_format_accepts_supported_values(value, expected):
    assert OutputFormat.parse(value) == expected


def test_output_format_rejects_unknown_value():
    with pytest.raises(ValueError, match="Unsupported output format"):
        OutputFormat.parse("gif")


def test_format_extension_maps_to_expected_suffix():
    assert format_extension(OutputFormat.HEIC) == ".heic"
    assert format_extension(OutputFormat.JPG) == ".jpg"
    assert format_extension(OutputFormat.PNG) == ".png"
    assert format_extension(OutputFormat.JXL) == ".jxl"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'photo_flow'`.

- [ ] **Step 3: Implement shared models**

Create `photo_flow/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `photo_flow/__main__.py`:

```python
from photo_flow.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `photo_flow/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class OutputFormat(StrEnum):
    HEIC = "heic"
    JPG = "jpg"
    PNG = "png"
    JXL = "jxl"

    @classmethod
    def parse(cls, value: str) -> "OutputFormat":
        normalized = value.strip().lower()
        if normalized == "jpeg":
            normalized = "jpg"
        try:
            return cls(normalized)
        except ValueError as exc:
            supported = ", ".join(item.value for item in cls)
            raise ValueError(f"Unsupported output format '{value}'. Supported: {supported}") from exc


def format_extension(output_format: OutputFormat) -> str:
    return {
        OutputFormat.HEIC: ".heic",
        OutputFormat.JPG: ".jpg",
        OutputFormat.PNG: ".png",
        OutputFormat.JXL: ".jxl",
    }[output_format]


@dataclass(frozen=True)
class AppConfig:
    raw_dir: Path
    original_heic_dir: Path
    tiff_dir: Path
    converted_output_dir: Path
    log_dir: Path
    default_format: OutputFormat
    default_quality: int
    overwrite_existing: bool
    raw_extensions: tuple[str, ...]
    backup_destinations: tuple[Path, ...]


@dataclass(frozen=True)
class SessionInventory:
    raw_files: tuple[Path, ...]
    original_heic_files: tuple[Path, ...]
    tiff_files: tuple[Path, ...]


@dataclass(frozen=True)
class ConversionPlan:
    source_tiff: Path
    output_file: Path
    output_format: OutputFormat
    quality: int


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow tests/test_models.py
git commit -m "feat: add shared photo-flow models"
```

---

## Task 3: Implement Config Loading

**Files:**
- Create: `photo_flow/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_config.py`:

```python
from pathlib import Path

import pytest
import yaml

from photo_flow.config import ConfigError, load_config
from photo_flow.models import OutputFormat


def write_config(path: Path, **overrides):
    data = {
        "raw_dir": str(path.parent / "raw"),
        "original_heic_dir": str(path.parent / "original_heic"),
        "tiff_dir": str(path.parent / "tiff"),
        "converted_output_dir": str(path.parent / "converted"),
        "log_dir": str(path.parent / "logs"),
        "default_format": "heic",
        "default_quality": 90,
        "overwrite_existing": False,
        "raw_extensions": [".arw", "CR3", ".dng"],
        "backup_destinations": [str(path.parent / "backup1"), str(path.parent / "backup2")],
    }
    data.update(overrides)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_load_config_normalizes_values(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)

    config = load_config(config_path)

    assert config.raw_dir == tmp_path / "raw"
    assert config.default_format == OutputFormat.HEIC
    assert config.default_quality == 90
    assert config.overwrite_existing is False
    assert config.raw_extensions == (".arw", ".cr3", ".dng")
    assert config.backup_destinations == (tmp_path / "backup1", tmp_path / "backup2")


def test_load_config_applies_defaults(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(
        config_path,
        default_format=None,
        default_quality=None,
        overwrite_existing=None,
        raw_extensions=None,
    )

    config = load_config(config_path)

    assert config.default_format == OutputFormat.HEIC
    assert config.default_quality == 90
    assert config.overwrite_existing is False
    assert config.raw_extensions == (".arw", ".cr3", ".nef", ".raf", ".rw2", ".dng")


def test_load_config_rejects_missing_required_field(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    del data["raw_dir"]
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ConfigError, match="Missing required config value: raw_dir"):
        load_config(config_path)


def test_load_config_rejects_bad_quality(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_config(config_path, default_quality=101)

    with pytest.raises(ConfigError, match="default_quality must be between 1 and 100"):
        load_config(config_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_config.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'photo_flow.config'`.

- [ ] **Step 3: Implement config loader**

Create `photo_flow/config.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from photo_flow.models import AppConfig, OutputFormat


DEFAULT_RAW_EXTENSIONS = (".arw", ".cr3", ".nef", ".raf", ".rw2", ".dng")


class ConfigError(ValueError):
    pass


def load_config(path: Path) -> AppConfig:
    try:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML config: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise ConfigError("Config file must contain a YAML mapping")

    data: dict[str, Any] = raw_data
    required = ("raw_dir", "original_heic_dir", "tiff_dir", "converted_output_dir", "log_dir", "backup_destinations")
    for key in required:
        if not data.get(key):
            raise ConfigError(f"Missing required config value: {key}")

    default_format = data.get("default_format") or "heic"
    try:
        output_format = OutputFormat.parse(str(default_format))
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    default_quality = data.get("default_quality")
    if default_quality is None:
        default_quality = 90
    try:
        quality = int(default_quality)
    except (TypeError, ValueError) as exc:
        raise ConfigError("default_quality must be an integer between 1 and 100") from exc
    if not 1 <= quality <= 100:
        raise ConfigError("default_quality must be between 1 and 100")

    overwrite_existing = bool(data.get("overwrite_existing") or False)
    raw_extensions = _normalize_extensions(data.get("raw_extensions") or DEFAULT_RAW_EXTENSIONS)
    destinations = data["backup_destinations"]
    if not isinstance(destinations, list) or not destinations:
        raise ConfigError("backup_destinations must be a non-empty list")

    return AppConfig(
        raw_dir=Path(data["raw_dir"]).expanduser(),
        original_heic_dir=Path(data["original_heic_dir"]).expanduser(),
        tiff_dir=Path(data["tiff_dir"]).expanduser(),
        converted_output_dir=Path(data["converted_output_dir"]).expanduser(),
        log_dir=Path(data["log_dir"]).expanduser(),
        default_format=output_format,
        default_quality=quality,
        overwrite_existing=overwrite_existing,
        raw_extensions=raw_extensions,
        backup_destinations=tuple(Path(item).expanduser() for item in destinations),
    )


def _normalize_extensions(values: object) -> tuple[str, ...]:
    if not isinstance(values, list | tuple):
        raise ConfigError("raw_extensions must be a list")
    normalized: list[str] = []
    for value in values:
        ext = str(value).strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.append(ext)
    if not normalized:
        raise ConfigError("raw_extensions must include at least one extension")
    return tuple(dict.fromkeys(normalized))
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow/config.py tests/test_config.py
git commit -m "feat: load photo-flow configuration"
```

---

## Task 4: Implement Session Scanning

**Files:**
- Create: `photo_flow/scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Write failing scanner tests**

Create `tests/test_scanner.py`:

```python
from pathlib import Path

import pytest

from photo_flow.models import AppConfig, OutputFormat
from photo_flow.scanner import ScanError, scan_session


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        raw_dir=tmp_path / "raw",
        original_heic_dir=tmp_path / "original_heic",
        tiff_dir=tmp_path / "tiff",
        converted_output_dir=tmp_path / "converted",
        log_dir=tmp_path / "logs",
        default_format=OutputFormat.HEIC,
        default_quality=90,
        overwrite_existing=False,
        raw_extensions=(".arw", ".cr3", ".dng"),
        backup_destinations=(tmp_path / "backup",),
    )


def touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def test_scan_session_collects_supported_files_sorted(tmp_path):
    config = make_config(tmp_path)
    touch(config.raw_dir / "DSC0002.ARW")
    touch(config.raw_dir / "DSC0001.cr3")
    touch(config.raw_dir / "ignore.txt")
    touch(config.original_heic_dir / "DSC0001.HEIC")
    touch(config.tiff_dir / "DSC0001.tif")
    touch(config.tiff_dir / "DSC0002.TIFF")
    config.converted_output_dir.mkdir()
    config.log_dir.mkdir()

    inventory = scan_session(config)

    assert [p.name for p in inventory.raw_files] == ["DSC0001.cr3", "DSC0002.ARW"]
    assert [p.name for p in inventory.original_heic_files] == ["DSC0001.HEIC"]
    assert [p.name for p in inventory.tiff_files] == ["DSC0001.tif", "DSC0002.TIFF"]


def test_scan_session_requires_source_directories(tmp_path):
    config = make_config(tmp_path)
    config.raw_dir.mkdir(parents=True)

    with pytest.raises(ScanError, match="Required directory does not exist"):
        scan_session(config)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_scanner.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'photo_flow.scanner'`.

- [ ] **Step 3: Implement scanner**

Create `photo_flow/scanner.py`:

```python
from __future__ import annotations

from pathlib import Path

from photo_flow.models import AppConfig, SessionInventory


TIFF_EXTENSIONS = (".tif", ".tiff")
HEIC_EXTENSIONS = (".heic", ".heif")


class ScanError(RuntimeError):
    pass


def scan_session(config: AppConfig) -> SessionInventory:
    for directory in (config.raw_dir, config.original_heic_dir, config.tiff_dir):
        if not directory.exists() or not directory.is_dir():
            raise ScanError(f"Required directory does not exist: {directory}")

    config.converted_output_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)

    return SessionInventory(
        raw_files=_files_with_extensions(config.raw_dir, config.raw_extensions),
        original_heic_files=_files_with_extensions(config.original_heic_dir, HEIC_EXTENSIONS),
        tiff_files=_files_with_extensions(config.tiff_dir, TIFF_EXTENSIONS),
    )


def _files_with_extensions(directory: Path, extensions: tuple[str, ...]) -> tuple[Path, ...]:
    normalized = {ext.lower() for ext in extensions}
    files = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in normalized
    ]
    return tuple(sorted(files, key=lambda item: item.name.lower()))
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_scanner.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow/scanner.py tests/test_scanner.py
git commit -m "feat: scan photo session files"
```

---

## Task 5: Add Command Runner and Dependency Checks

**Files:**
- Create: `photo_flow/commands.py`
- Create: `photo_flow/dependencies.py`
- Create: `tests/test_dependencies.py`

- [ ] **Step 1: Write failing dependency tests**

Create `tests/test_dependencies.py`:

```python
from photo_flow.dependencies import missing_tools, required_tools_for
from photo_flow.models import OutputFormat


def test_required_tools_for_heic_includes_metadata_and_trash_tools():
    tools = required_tools_for(OutputFormat.HEIC, encrypted_backup=True)

    assert tools == ("exiftool", "magick", "7z", "trash")


def test_required_tools_for_jxl_uses_cjxl():
    tools = required_tools_for(OutputFormat.JXL, encrypted_backup=False)

    assert tools == ("exiftool", "cjxl", "zip", "trash")


def test_missing_tools_reports_only_absent_tools():
    calls = {"exiftool": "/opt/homebrew/bin/exiftool", "magick": None}

    assert missing_tools(("exiftool", "magick"), resolver=calls.get) == ("magick",)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_dependencies.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'photo_flow.dependencies'`.

- [ ] **Step 3: Implement command runner and dependencies**

Create `photo_flow/commands.py`:

```python
from __future__ import annotations

import subprocess
from collections.abc import Sequence

from photo_flow.models import CommandResult


class CommandError(RuntimeError):
    def __init__(self, result: CommandResult):
        self.result = result
        command = " ".join(result.args)
        super().__init__(f"Command failed ({result.returncode}): {command}\n{result.stderr}")


def run_command(args: Sequence[str], *, check: bool = True) -> CommandResult:
    completed = subprocess.run(
        list(args),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = CommandResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and not result.ok:
        raise CommandError(result)
    return result
```

Create `photo_flow/dependencies.py`:

```python
from __future__ import annotations

import shutil
from collections.abc import Callable

from photo_flow.models import OutputFormat


def required_tools_for(output_format: OutputFormat, *, encrypted_backup: bool) -> tuple[str, ...]:
    conversion_tool = "cjxl" if output_format is OutputFormat.JXL else "magick"
    archive_tool = "7z" if encrypted_backup else "zip"
    return ("exiftool", conversion_tool, archive_tool, "trash")


def missing_tools(
    tools: tuple[str, ...],
    *,
    resolver: Callable[[str], str | None] = shutil.which,
) -> tuple[str, ...]:
    return tuple(tool for tool in tools if resolver(tool) is None)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_dependencies.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow/commands.py photo_flow/dependencies.py tests/test_dependencies.py
git commit -m "feat: check external tool dependencies"
```

---

## Task 6: Implement Conversion Planning and Commands

**Files:**
- Create: `photo_flow/converter.py`
- Create: `tests/test_converter.py`

- [ ] **Step 1: Write failing converter tests**

Create `tests/test_converter.py`:

```python
from pathlib import Path

import pytest

from photo_flow.converter import ConversionError, build_conversion_command, build_conversion_plans
from photo_flow.models import ConversionPlan, OutputFormat


def test_build_conversion_plans_uses_exact_basename_and_extension(tmp_path):
    source = tmp_path / "tiff" / "DSC0001.tif"
    source.parent.mkdir()
    source.write_bytes(b"tiff")
    output_dir = tmp_path / "converted"
    output_dir.mkdir()

    plans = build_conversion_plans(
        (source,),
        output_dir=output_dir,
        output_format=OutputFormat.HEIC,
        quality=90,
        overwrite=False,
    )

    assert plans == (
        ConversionPlan(source, output_dir / "DSC0001.heic", OutputFormat.HEIC, 90),
    )


def test_build_conversion_plans_refuses_existing_output_without_overwrite(tmp_path):
    source = tmp_path / "DSC0001.tif"
    output = tmp_path / "converted" / "DSC0001.jpg"
    source.write_bytes(b"tiff")
    output.parent.mkdir()
    output.write_bytes(b"existing")

    with pytest.raises(ConversionError, match="Output file already exists"):
        build_conversion_plans(
            (source,),
            output_dir=output.parent,
            output_format=OutputFormat.JPG,
            quality=85,
            overwrite=False,
        )


def test_build_heic_command_uses_magick_quality_define():
    plan = ConversionPlan(Path("in.tif"), Path("out.heic"), OutputFormat.HEIC, 90)

    assert build_conversion_command(plan) == (
        "magick",
        "in.tif",
        "-quality",
        "90",
        "out.heic",
    )


def test_build_jxl_command_uses_cjxl():
    plan = ConversionPlan(Path("in.tif"), Path("out.jxl"), OutputFormat.JXL, 80)

    assert build_conversion_command(plan) == (
        "cjxl",
        "in.tif",
        "out.jxl",
        "-q",
        "80",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_converter.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'photo_flow.converter'`.

- [ ] **Step 3: Implement converter**

Create `photo_flow/converter.py`:

```python
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from photo_flow.commands import run_command
from photo_flow.models import CommandResult, ConversionPlan, OutputFormat, format_extension


class ConversionError(RuntimeError):
    pass


def build_conversion_plans(
    tiff_files: Sequence[Path],
    *,
    output_dir: Path,
    output_format: OutputFormat,
    quality: int,
    overwrite: bool,
) -> tuple[ConversionPlan, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plans: list[ConversionPlan] = []
    for tiff_file in tiff_files:
        output_file = output_dir / f"{tiff_file.stem}{format_extension(output_format)}"
        if output_file.exists() and not overwrite:
            raise ConversionError(f"Output file already exists: {output_file}")
        plans.append(ConversionPlan(tiff_file, output_file, output_format, quality))
    return tuple(plans)


def build_conversion_command(plan: ConversionPlan) -> tuple[str, ...]:
    if plan.output_format is OutputFormat.JXL:
        return ("cjxl", str(plan.source_tiff), str(plan.output_file), "-q", str(plan.quality))
    if plan.output_format is OutputFormat.PNG:
        return ("magick", str(plan.source_tiff), str(plan.output_file))
    return (
        "magick",
        str(plan.source_tiff),
        "-quality",
        str(plan.quality),
        str(plan.output_file),
    )


def convert_all(
    plans: Sequence[ConversionPlan],
    *,
    runner: Callable[[Sequence[str]], CommandResult] | None = None,
) -> tuple[CommandResult, ...]:
    command_runner = runner or (lambda args: run_command(args, check=True))
    results: list[CommandResult] = []
    for plan in plans:
        results.append(command_runner(build_conversion_command(plan)))
    return tuple(results)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_converter.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow/converter.py tests/test_converter.py
git commit -m "feat: plan photo conversions"
```

---

## Task 7: Implement Size Estimation

**Files:**
- Create: `photo_flow/estimator.py`
- Create: `tests/test_estimator.py`

- [ ] **Step 1: Write failing estimator tests**

Create `tests/test_estimator.py`:

```python
from pathlib import Path

from photo_flow.estimator import EstimateResult, choose_sample_files, estimate_total_size


def make_file(path: Path, size: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_choose_sample_files_spreads_across_list(tmp_path):
    files = []
    for index in range(10):
        path = tmp_path / f"{index:02d}.tif"
        make_file(path, 10)
        files.append(path)

    sample = choose_sample_files(tuple(files), max_samples=5)

    assert [item.name for item in sample] == ["00.tif", "02.tif", "04.tif", "06.tif", "09.tif"]


def test_estimate_total_size_extrapolates_from_sample_sizes(tmp_path):
    all_files = []
    for index, size in enumerate([100, 200, 300, 400]):
        path = tmp_path / f"{index}.tif"
        make_file(path, size)
        all_files.append(path)
    sample_outputs = []
    for index, size in enumerate([10, 20]):
        path = tmp_path / f"out-{index}.heic"
        make_file(path, size)
        sample_outputs.append(path)

    result = estimate_total_size(tuple(all_files), tuple(all_files[:2]), tuple(sample_outputs))

    assert result == EstimateResult(
        sample_count=2,
        sample_input_bytes=300,
        sample_output_bytes=30,
        total_input_bytes=1000,
        estimated_output_bytes=100,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_estimator.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'photo_flow.estimator'`.

- [ ] **Step 3: Implement estimator math**

Create `photo_flow/estimator.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EstimateResult:
    sample_count: int
    sample_input_bytes: int
    sample_output_bytes: int
    total_input_bytes: int
    estimated_output_bytes: int


def choose_sample_files(files: tuple[Path, ...], *, max_samples: int = 5) -> tuple[Path, ...]:
    if len(files) <= max_samples:
        return files
    if max_samples <= 1:
        return (files[0],)
    last_index = len(files) - 1
    indexes = [round(index * last_index / (max_samples - 1)) for index in range(max_samples)]
    return tuple(files[index] for index in indexes)


def estimate_total_size(
    all_input_files: tuple[Path, ...],
    sample_input_files: tuple[Path, ...],
    sample_output_files: tuple[Path, ...],
) -> EstimateResult:
    sample_input_bytes = sum(path.stat().st_size for path in sample_input_files)
    sample_output_bytes = sum(path.stat().st_size for path in sample_output_files)
    total_input_bytes = sum(path.stat().st_size for path in all_input_files)
    if sample_input_bytes == 0:
        estimated = 0
    else:
        estimated = round(total_input_bytes * (sample_output_bytes / sample_input_bytes))
    return EstimateResult(
        sample_count=len(sample_input_files),
        sample_input_bytes=sample_input_bytes,
        sample_output_bytes=sample_output_bytes,
        total_input_bytes=total_input_bytes,
        estimated_output_bytes=estimated,
    )


def format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{value} B"
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_estimator.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow/estimator.py tests/test_estimator.py
git commit -m "feat: estimate converted output size"
```

---

## Task 8: Implement Metadata and Integrity Checks

**Files:**
- Create: `photo_flow/metadata.py`
- Create: `photo_flow/integrity.py`
- Create: `tests/test_metadata_integrity.py`

- [ ] **Step 1: Write failing metadata and integrity tests**

Create `tests/test_metadata_integrity.py`:

```python
from pathlib import Path

from photo_flow.integrity import IntegrityError, verify_converted_file
from photo_flow.metadata import build_copy_metadata_command, build_read_metadata_command
from photo_flow.models import ConversionPlan, OutputFormat


def test_copy_metadata_command_preserves_original_output_file():
    plan = ConversionPlan(Path("source.tif"), Path("out.heic"), OutputFormat.HEIC, 90)

    assert build_copy_metadata_command(plan) == (
        "exiftool",
        "-TagsFromFile",
        "source.tif",
        "-all:all",
        "-overwrite_original",
        "out.heic",
    )


def test_read_metadata_command_uses_json_output():
    assert build_read_metadata_command(Path("out.heic")) == ("exiftool", "-json", "out.heic")


def test_verify_converted_file_reports_missing_file(tmp_path):
    errors = verify_converted_file(tmp_path / "missing.heic")

    assert errors == (IntegrityError(path=tmp_path / "missing.heic", reason="file is missing"),)


def test_verify_converted_file_reports_empty_file(tmp_path):
    output = tmp_path / "empty.heic"
    output.write_bytes(b"")

    errors = verify_converted_file(output)

    assert errors == (IntegrityError(path=output, reason="file is empty"),)


def test_verify_converted_file_passes_non_empty_file(tmp_path):
    output = tmp_path / "ok.heic"
    output.write_bytes(b"image")

    assert verify_converted_file(output) == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_metadata_integrity.py -q
```

Expected: FAIL with `ModuleNotFoundError` for metadata or integrity.

- [ ] **Step 3: Implement metadata and integrity modules**

Create `photo_flow/metadata.py`:

```python
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from photo_flow.commands import run_command
from photo_flow.models import CommandResult, ConversionPlan


def build_copy_metadata_command(plan: ConversionPlan) -> tuple[str, ...]:
    return (
        "exiftool",
        "-TagsFromFile",
        str(plan.source_tiff),
        "-all:all",
        "-overwrite_original",
        str(plan.output_file),
    )


def build_read_metadata_command(path: Path) -> tuple[str, ...]:
    return ("exiftool", "-json", str(path))


def copy_metadata(
    plans: Sequence[ConversionPlan],
    *,
    runner: Callable[[Sequence[str]], CommandResult] | None = None,
) -> tuple[CommandResult, ...]:
    command_runner = runner or (lambda args: run_command(args, check=True))
    return tuple(command_runner(build_copy_metadata_command(plan)) for plan in plans)


def read_metadata(
    path: Path,
    *,
    runner: Callable[[Sequence[str]], CommandResult] | None = None,
) -> CommandResult:
    command_runner = runner or (lambda args: run_command(args, check=True))
    return command_runner(build_read_metadata_command(path))
```

Create `photo_flow/integrity.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IntegrityError:
    path: Path
    reason: str


def verify_converted_file(path: Path) -> tuple[IntegrityError, ...]:
    if not path.exists():
        return (IntegrityError(path=path, reason="file is missing"),)
    if not path.is_file():
        return (IntegrityError(path=path, reason="path is not a file"),)
    if path.stat().st_size <= 0:
        return (IntegrityError(path=path, reason="file is empty"),)
    return ()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_metadata_integrity.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow/metadata.py photo_flow/integrity.py tests/test_metadata_integrity.py
git commit -m "feat: copy metadata and check outputs"
```

---

## Task 9: Implement Backup Manifest and Archive Planning

**Files:**
- Create: `photo_flow/backup.py`
- Create: `tests/test_backup.py`

- [ ] **Step 1: Write failing backup tests**

Create `tests/test_backup.py`:

```python
from datetime import date, datetime, timezone
from pathlib import Path

from photo_flow.backup import (
    BackupPlan,
    archive_name,
    build_archive_command,
    copy_to_existing_destinations,
    create_manifest,
    sha256_file,
)
from photo_flow.models import OutputFormat


def test_archive_name_uses_date_tags_and_extension():
    assert archive_name(date(2026, 6, 10), ("japan", "street"), encrypted=False) == "2026-06-10_japan_street.zip"
    assert archive_name(date(2026, 6, 10), ("private",), encrypted=True) == "2026-06-10_private.7z"
    assert archive_name(date(2026, 6, 10), (), encrypted=False) == "2026-06-10.zip"


def test_sha256_file_hashes_content(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("abc", encoding="utf-8")

    assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_create_manifest_lists_files_and_hashes(tmp_path):
    raw = tmp_path / "DSC0001.ARW"
    raw.write_bytes(b"raw")
    manifest = create_manifest(
        timestamp=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
        output_format=OutputFormat.HEIC,
        quality=90,
        source_dirs={"raw_dir": tmp_path},
        converted_output_dir=tmp_path / "converted",
        backup_destinations=(tmp_path / "backup",),
        files=(raw,),
        tool_versions={"exiftool": "exiftool 13.0"},
        warnings=("missing destination",),
        verification_results=("DSC0001.heic ok",),
    )

    assert manifest["output_format"] == "heic"
    assert manifest["files"][0]["path"] == str(raw)
    assert manifest["files"][0]["sha256"] == sha256_file(raw)


def test_build_archive_command_uses_zip_for_unencrypted(tmp_path):
    plan = BackupPlan(archive_path=tmp_path / "backup.zip", staging_dir=tmp_path / "stage", encrypted=False)

    assert build_archive_command(plan, password=None) == (
        "zip",
        "-r",
        str(tmp_path / "backup.zip"),
        ".",
    )


def test_build_archive_command_uses_7z_for_encrypted(tmp_path):
    plan = BackupPlan(archive_path=tmp_path / "backup.7z", staging_dir=tmp_path / "stage", encrypted=True)

    assert build_archive_command(plan, password="secret") == (
        "7z",
        "a",
        "-t7z",
        "-mhe=on",
        "-psecret",
        str(tmp_path / "backup.7z"),
        ".",
    )


def test_copy_to_existing_destinations_skips_missing_paths(tmp_path):
    archive = tmp_path / "backup.zip"
    archive.write_bytes(b"archive")
    existing = tmp_path / "existing"
    existing.mkdir()
    missing = tmp_path / "missing"

    copied, warnings = copy_to_existing_destinations(archive, (existing, missing))

    assert copied == (existing / "backup.zip",)
    assert (existing / "backup.zip").read_bytes() == b"archive"
    assert warnings == (f"Backup destination does not exist: {missing}",)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_backup.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'photo_flow.backup'`.

- [ ] **Step 3: Implement backup module**

Create `photo_flow/backup.py`:

```python
from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from photo_flow.models import OutputFormat


@dataclass(frozen=True)
class BackupPlan:
    archive_path: Path
    staging_dir: Path
    encrypted: bool


def archive_name(run_date: date, tags: Sequence[str], *, encrypted: bool) -> str:
    clean_tags = tuple(_clean_tag(tag) for tag in tags if _clean_tag(tag))
    suffix = ".7z" if encrypted else ".zip"
    if clean_tags:
        return f"{run_date.isoformat()}_{'_'.join(clean_tags)}{suffix}"
    return f"{run_date.isoformat()}{suffix}"


def _clean_tag(tag: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in tag.strip())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_manifest(
    *,
    timestamp: datetime,
    output_format: OutputFormat,
    quality: int,
    source_dirs: Mapping[str, Path],
    converted_output_dir: Path,
    backup_destinations: Sequence[Path],
    files: Sequence[Path],
    tool_versions: Mapping[str, str],
    warnings: Sequence[str],
    verification_results: Sequence[str],
) -> dict[str, object]:
    return {
        "timestamp": timestamp.isoformat(),
        "output_format": output_format.value,
        "quality": quality,
        "source_dirs": {key: str(value) for key, value in source_dirs.items()},
        "converted_output_dir": str(converted_output_dir),
        "backup_destinations": [str(path) for path in backup_destinations],
        "tool_versions": dict(tool_versions),
        "warnings": list(warnings),
        "verification_results": list(verification_results),
        "files": [
            {
                "path": str(path),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }


def write_manifest(path: Path, manifest: Mapping[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def build_archive_command(plan: BackupPlan, *, password: str | None) -> tuple[str, ...]:
    if plan.encrypted:
        if not password:
            raise ValueError("Encrypted backups require a password")
        return ("7z", "a", "-t7z", "-mhe=on", f"-p{password}", str(plan.archive_path), ".")
    return ("zip", "-r", str(plan.archive_path), ".")


def copy_to_existing_destinations(archive_path: Path, destinations: Sequence[Path]) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    copied: list[Path] = []
    warnings: list[str] = []
    for destination in destinations:
        if not destination.exists() or not destination.is_dir():
            warnings.append(f"Backup destination does not exist: {destination}")
            continue
        target = destination / archive_path.name
        shutil.copy2(archive_path, target)
        copied.append(target)
    return tuple(copied), tuple(warnings)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_backup.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow/backup.py tests/test_backup.py
git commit -m "feat: plan backup archives"
```

---

## Task 10: Implement Trash and Logging

**Files:**
- Create: `photo_flow/trash.py`
- Create: `photo_flow/logging_setup.py`
- Create: `tests/test_trash_logging.py`

- [ ] **Step 1: Write failing trash/logging tests**

Create `tests/test_trash_logging.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_trash_logging.py -q
```

Expected: FAIL with `ModuleNotFoundError` for trash or logging setup.

- [ ] **Step 3: Implement trash and logging**

Create `photo_flow/trash.py`:

```python
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from photo_flow.commands import run_command
from photo_flow.models import CommandResult


def build_trash_command(paths: Sequence[Path]) -> tuple[str, ...]:
    return ("trash", *(str(path) for path in paths))


def trash_files(
    paths: Sequence[Path],
    *,
    runner: Callable[[Sequence[str]], CommandResult] | None = None,
) -> CommandResult:
    command_runner = runner or (lambda args: run_command(args, check=True))
    return command_runner(build_trash_command(paths))
```

Create `photo_flow/logging_setup.py`:

```python
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def log_path_for_run(log_dir: Path, timestamp: datetime) -> Path:
    return log_dir / f"photo-flow-{timestamp:%Y%m%d-%H%M%S}.log"


def configure_logging(log_dir: Path, timestamp: datetime) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_path_for_run(log_dir, timestamp)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_trash_logging.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow/trash.py photo_flow/logging_setup.py tests/test_trash_logging.py
git commit -m "feat: add trash and logging helpers"
```

---

## Task 11: Implement CLI Estimate Command

**Files:**
- Create: `photo_flow/cli.py`
- Create: `tests/test_cli_estimate.py`

- [ ] **Step 1: Write failing CLI estimate tests**

Create `tests/test_cli_estimate.py`:

```python
import yaml

from photo_flow.cli import main


def test_estimate_command_prints_estimate(tmp_path, capsys):
    raw = tmp_path / "raw"
    heic = tmp_path / "heic"
    tiff = tmp_path / "tiff"
    converted = tmp_path / "converted"
    logs = tmp_path / "logs"
    backup = tmp_path / "backup"
    for directory in (raw, heic, tiff, converted, logs, backup):
        directory.mkdir()
    (tiff / "DSC0001.tif").write_bytes(b"x" * 100)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "raw_dir": str(raw),
                "original_heic_dir": str(heic),
                "tiff_dir": str(tiff),
                "converted_output_dir": str(converted),
                "log_dir": str(logs),
                "backup_destinations": [str(backup)],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["estimate", "--config", str(config_path), "--dry-sample-size", "40"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Estimated converted output size" in captured.out
    assert "heic" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_cli_estimate.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'photo_flow.cli'`.

- [ ] **Step 3: Implement estimate command**

Create `photo_flow/cli.py`:

```python
from __future__ import annotations

import argparse
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Sequence

from photo_flow.config import ConfigError, load_config
from photo_flow.converter import build_conversion_plans, convert_all
from photo_flow.estimator import choose_sample_files, estimate_total_size, format_bytes
from photo_flow.models import OutputFormat
from photo_flow.scanner import ScanError, scan_session


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "estimate":
            return estimate_command(args)
        if args.command == "run":
            return run_command(args)
    except (ConfigError, ScanError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}")
        return 1
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="photo-flow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    estimate = subparsers.add_parser("estimate", help="estimate converted output size")
    add_common_options(estimate)
    estimate.add_argument("--dry-sample-size", type=int, default=0, help=argparse.SUPPRESS)

    run = subparsers.add_parser("run", help="run conversion, cleanup, and backup workflow")
    add_common_options(run)
    run.add_argument("--tags", default="", help="comma-separated tags for the backup name")
    run.add_argument("--encrypt", action="store_true", help="create encrypted .7z backup")
    run.add_argument("--yes", action="store_true", help="auto-confirm non-destructive prompts")
    return parser


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--format", dest="output_format", choices=["heic", "jpg", "jpeg", "png", "jxl"])
    parser.add_argument("--quality", type=int)
    parser.add_argument("--overwrite", action="store_true")


def resolve_format_and_quality(args: argparse.Namespace, config) -> tuple[OutputFormat, int]:
    output_format = OutputFormat.parse(args.output_format) if args.output_format else config.default_format
    quality = args.quality if args.quality is not None else config.default_quality
    if not 1 <= quality <= 100:
        raise ValueError("quality must be between 1 and 100")
    return output_format, quality


def estimate_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output_format, quality = resolve_format_and_quality(args, config)
    inventory = scan_session(config)
    samples = choose_sample_files(inventory.tiff_files)
    if not samples:
        print("No TIFF files found.")
        return 0

    with tempfile.TemporaryDirectory(prefix="photo-flow-estimate-") as temp_dir:
        temp_output_dir = Path(temp_dir)
        plans = build_conversion_plans(
            samples,
            output_dir=temp_output_dir,
            output_format=output_format,
            quality=quality,
            overwrite=True,
        )
        if args.dry_sample_size:
            for plan in plans:
                plan.output_file.write_bytes(b"x" * args.dry_sample_size)
        else:
            convert_all(plans)
        result = estimate_total_size(
            inventory.tiff_files,
            samples,
            tuple(plan.output_file for plan in plans),
        )

    print(f"Format: {output_format.value}")
    print(f"Quality: {quality}")
    print(f"Sample files: {result.sample_count}")
    print(f"Sample input size: {format_bytes(result.sample_input_bytes)}")
    print(f"Sample output size: {format_bytes(result.sample_output_bytes)}")
    print(f"Estimated converted output size: {format_bytes(result.estimated_output_bytes)}")
    return 0


def run_command(args: argparse.Namespace) -> int:
    raise RuntimeError("run command is unavailable until Task 12")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_cli_estimate.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow/cli.py tests/test_cli_estimate.py
git commit -m "feat: add estimate command"
```

---

## Task 12: Implement CLI Run Orchestration

**Files:**
- Modify: `photo_flow/cli.py`
- Create: `tests/test_cli_run.py`

- [ ] **Step 1: Write failing CLI run tests**

Create `tests/test_cli_run.py`:

```python
import yaml

from photo_flow.cli import main


def make_config(tmp_path):
    raw = tmp_path / "raw"
    heic = tmp_path / "heic"
    tiff = tmp_path / "tiff"
    converted = tmp_path / "converted"
    logs = tmp_path / "logs"
    backup = tmp_path / "backup"
    for directory in (raw, heic, tiff, converted, logs, backup):
        directory.mkdir()
    (raw / "DSC0001.ARW").write_bytes(b"raw")
    (heic / "DSC0001.heic").write_bytes(b"original")
    (tiff / "DSC0001.tif").write_bytes(b"tiff")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "raw_dir": str(raw),
                "original_heic_dir": str(heic),
                "tiff_dir": str(tiff),
                "converted_output_dir": str(converted),
                "log_dir": str(logs),
                "backup_destinations": [str(backup)],
            }
        ),
        encoding="utf-8",
    )
    return config_path, converted, logs, backup


def test_run_command_dry_run_completes_without_external_tools(tmp_path, capsys):
    config_path, converted, logs, backup = make_config(tmp_path)

    exit_code = main([
        "run",
        "--config",
        str(config_path),
        "--tags",
        "test",
        "--yes",
        "--dry-run",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Dry run completed" in captured.out
    assert "DSC0001.heic" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_cli_run.py -q
```

Expected: FAIL because `--dry-run` is not recognized or `run command is unavailable until Task 12`.

- [ ] **Step 3: Implement run orchestration with dry-run mode**

Modify `photo_flow/cli.py`:

```python
from __future__ import annotations

import argparse
import getpass
import json
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from photo_flow.backup import archive_name, copy_to_existing_destinations, create_manifest, write_manifest
from photo_flow.config import ConfigError, load_config
from photo_flow.converter import build_conversion_plans, convert_all
from photo_flow.dependencies import missing_tools, required_tools_for
from photo_flow.estimator import choose_sample_files, estimate_total_size, format_bytes
from photo_flow.integrity import verify_converted_file
from photo_flow.logging_setup import configure_logging
from photo_flow.metadata import copy_metadata, read_metadata
from photo_flow.models import OutputFormat
from photo_flow.scanner import ScanError, scan_session
from photo_flow.trash import trash_files


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "estimate":
            return estimate_command(args)
        if args.command == "run":
            return run_command(args)
    except (ConfigError, ScanError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}")
        return 1
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="photo-flow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    estimate = subparsers.add_parser("estimate", help="estimate converted output size")
    add_common_options(estimate)
    estimate.add_argument("--dry-sample-size", type=int, default=0, help=argparse.SUPPRESS)

    run = subparsers.add_parser("run", help="run conversion, cleanup, and backup workflow")
    add_common_options(run)
    run.add_argument("--tags", default="", help="comma-separated tags for the backup name")
    run.add_argument("--encrypt", action="store_true", help="create encrypted .7z backup")
    run.add_argument("--yes", action="store_true", help="auto-confirm non-destructive prompts")
    run.add_argument("--dry-run", action="store_true", help="print planned work without external tool execution")
    return parser


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--format", dest="output_format", choices=["heic", "jpg", "jpeg", "png", "jxl"])
    parser.add_argument("--quality", type=int)
    parser.add_argument("--overwrite", action="store_true")


def resolve_format_and_quality(args: argparse.Namespace, config) -> tuple[OutputFormat, int]:
    output_format = OutputFormat.parse(args.output_format) if args.output_format else config.default_format
    quality = args.quality if args.quality is not None else config.default_quality
    if not 1 <= quality <= 100:
        raise ValueError("quality must be between 1 and 100")
    return output_format, quality


def estimate_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output_format, quality = resolve_format_and_quality(args, config)
    inventory = scan_session(config)
    samples = choose_sample_files(inventory.tiff_files)
    if not samples:
        print("No TIFF files found.")
        return 0

    with tempfile.TemporaryDirectory(prefix="photo-flow-estimate-") as temp_dir:
        temp_output_dir = Path(temp_dir)
        plans = build_conversion_plans(
            samples,
            output_dir=temp_output_dir,
            output_format=output_format,
            quality=quality,
            overwrite=True,
        )
        if args.dry_sample_size:
            for plan in plans:
                plan.output_file.write_bytes(b"x" * args.dry_sample_size)
        else:
            convert_all(plans)
        result = estimate_total_size(
            inventory.tiff_files,
            samples,
            tuple(plan.output_file for plan in plans),
        )

    print(f"Format: {output_format.value}")
    print(f"Quality: {quality}")
    print(f"Sample files: {result.sample_count}")
    print(f"Sample input size: {format_bytes(result.sample_input_bytes)}")
    print(f"Sample output size: {format_bytes(result.sample_output_bytes)}")
    print(f"Estimated converted output size: {format_bytes(result.estimated_output_bytes)}")
    return 0


def run_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output_format, quality = resolve_format_and_quality(args, config)
    inventory = scan_session(config)
    overwrite = args.overwrite or config.overwrite_existing
    plans = build_conversion_plans(
        inventory.tiff_files,
        output_dir=config.converted_output_dir,
        output_format=output_format,
        quality=quality,
        overwrite=overwrite,
    )
    tags = tuple(tag.strip() for tag in args.tags.split(",") if tag.strip())

    if args.dry_run:
        print("Dry run completed. Planned converted files:")
        for plan in plans:
            print(f"- {plan.source_tiff.name} -> {plan.output_file.name}")
        return 0

    missing = missing_tools(required_tools_for(output_format, encrypted_backup=args.encrypt))
    if missing:
        raise RuntimeError(f"Missing required tools: {', '.join(missing)}")

    timestamp = datetime.now(timezone.utc)
    log_path = configure_logging(config.log_dir, timestamp)
    logging.info("Starting photo-flow run")

    if output_format is OutputFormat.PNG:
        logging.warning("PNG output is lossless; quality setting is ignored by conversion")
        print("Warning: PNG output is lossless; quality setting is ignored.")

    if not confirm(f"Convert {len(plans)} TIFF files to {output_format.value}?", assume_yes=args.yes):
        print("Conversion cancelled.")
        return 1

    convert_all(plans)
    copy_metadata(plans)
    verification_messages = []
    for plan in plans:
        errors = verify_converted_file(plan.output_file)
        if errors:
            for error in errors:
                logging.error("%s: %s", error.path, error.reason)
            raise RuntimeError("Converted file verification failed")
        read_metadata(plan.output_file)
        verification_messages.append(f"{plan.output_file.name} ok")

    if confirm(f"Move {len(inventory.tiff_files)} TIFF files to macOS Trash?", assume_yes=False):
        trash_files(inventory.tiff_files)
        for path in inventory.tiff_files:
            logging.info("Trashed TIFF: %s", path)

    archive_password = None
    if args.encrypt:
        archive_password = prompt_password()

    with tempfile.TemporaryDirectory(prefix="photo-flow-backup-") as staging:
        staging_dir = Path(staging)
        files_to_backup = (*inventory.raw_files, *inventory.original_heic_files, *(plan.output_file for plan in plans), log_path)
        manifest = create_manifest(
            timestamp=timestamp,
            output_format=output_format,
            quality=quality,
            source_dirs={
                "raw_dir": config.raw_dir,
                "original_heic_dir": config.original_heic_dir,
                "tiff_dir": config.tiff_dir,
            },
            converted_output_dir=config.converted_output_dir,
            backup_destinations=config.backup_destinations,
            files=files_to_backup,
            tool_versions={},
            warnings=(),
            verification_results=tuple(verification_messages),
        )
        write_manifest(staging_dir / "manifest.json", manifest)
        for source in files_to_backup:
            target = staging_dir / source.name
            shutil.copy2(source, target)
        local_archive = config.log_dir / archive_name(timestamp.date(), tags, encrypted=args.encrypt)
        if args.encrypt:
            import subprocess

            subprocess.run(["7z", "a", "-t7z", "-mhe=on", f"-p{archive_password}", str(local_archive), "."], cwd=staging_dir, check=True)
        else:
            shutil.make_archive(str(local_archive.with_suffix("")), "zip", staging_dir)
        copied, warnings = copy_to_existing_destinations(local_archive, config.backup_destinations)
        for warning in warnings:
            logging.warning(warning)
            print(f"Warning: {warning}")

    print(f"Backup created: {local_archive}")
    for path in copied:
        print(f"Backup copied: {path}")
    return 0


def confirm(prompt: str, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    response = input(f"{prompt} [y/N] ").strip().lower()
    return response in {"y", "yes"}


def prompt_password() -> str:
    first = getpass.getpass("Backup password: ")
    second = getpass.getpass("Confirm backup password: ")
    if first != second:
        raise RuntimeError("Backup passwords do not match")
    if not first:
        raise RuntimeError("Backup password cannot be empty")
    return first
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_cli_run.py -q
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add photo_flow/cli.py tests/test_cli_run.py
git commit -m "feat: orchestrate photo-flow run command"
```

---

## Task 13: Tighten Real Tool Integration

**Files:**
- Modify: `photo_flow/integrity.py`
- Modify: `photo_flow/backup.py`
- Modify: `photo_flow/cli.py`
- Create: `tests/test_tool_integration_planning.py`

- [ ] **Step 1: Write failing tests for command planning gaps**

Create `tests/test_tool_integration_planning.py`:

```python
from pathlib import Path

from photo_flow.backup import BackupPlan, build_archive_command
from photo_flow.integrity import build_identify_command


def test_build_identify_command_uses_magick_identify():
    assert build_identify_command(Path("out.heic")) == ("magick", "identify", "out.heic")


def test_build_archive_command_accepts_hidden_password_flag():
    plan = BackupPlan(archive_path=Path("backup.7z"), staging_dir=Path("stage"), encrypted=True)

    assert build_archive_command(plan, password="secret") == (
        "7z",
        "a",
        "-t7z",
        "-mhe=on",
        "-psecret",
        "backup.7z",
        ".",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_tool_integration_planning.py -q
```

Expected: FAIL with `ImportError: cannot import name 'build_identify_command'`.

- [ ] **Step 3: Add identify command helper and route archive creation through backup command builder**

Modify `photo_flow/integrity.py`:

```python
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from photo_flow.commands import run_command
from photo_flow.models import CommandResult


@dataclass(frozen=True)
class IntegrityError:
    path: Path
    reason: str


def build_identify_command(path: Path) -> tuple[str, ...]:
    return ("magick", "identify", str(path))


def verify_converted_file(path: Path) -> tuple[IntegrityError, ...]:
    if not path.exists():
        return (IntegrityError(path=path, reason="file is missing"),)
    if not path.is_file():
        return (IntegrityError(path=path, reason="path is not a file"),)
    if path.stat().st_size <= 0:
        return (IntegrityError(path=path, reason="file is empty"),)
    return ()


def identify_image(
    path: Path,
    *,
    runner: Callable[[Sequence[str]], CommandResult] | None = None,
) -> CommandResult:
    command_runner = runner or (lambda args: run_command(args, check=True))
    return command_runner(build_identify_command(path))
```

Modify the imports in `photo_flow/cli.py`:

```python
from photo_flow.backup import BackupPlan, archive_name, build_archive_command, copy_to_existing_destinations, create_manifest, write_manifest
from photo_flow.commands import run_command as run_external_command
from photo_flow.integrity import identify_image, verify_converted_file
```

Modify the verification loop in `photo_flow/cli.py`:

```python
        read_metadata(plan.output_file)
        identify_image(plan.output_file)
        verification_messages.append(f"{plan.output_file.name} ok")
```

Modify the archive creation block in `photo_flow/cli.py`:

```python
        local_archive = config.log_dir / archive_name(timestamp.date(), tags, encrypted=args.encrypt)
        if args.encrypt:
            backup_plan = BackupPlan(archive_path=local_archive, staging_dir=staging_dir, encrypted=True)
            run_external_command(build_archive_command(backup_plan, password=archive_password), check=True)
        else:
            shutil.make_archive(str(local_archive.with_suffix("")), "zip", staging_dir)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_tool_integration_planning.py tests/test_metadata_integrity.py tests/test_cli_run.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add photo_flow/integrity.py photo_flow/cli.py tests/test_tool_integration_planning.py
git commit -m "feat: verify images with external identify command"
```

---

## Task 14: Add End-User Documentation and Final Verification

**Files:**
- Modify: `README.md`
- Modify: `config.example.yaml`

- [ ] **Step 1: Update README with complete usage**

Modify `README.md`:

```markdown
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
```

- [ ] **Step 2: Add comments to example config**

Modify `config.example.yaml`:

```yaml
# One run should point at one photo session.
raw_dir: /path/to/session/raw
original_heic_dir: /path/to/session/original_heic
tiff_dir: /path/to/session/tiff_exports
converted_output_dir: /path/to/session/converted
log_dir: /path/to/photo-flow/logs

# Supported formats: heic, jpg, png, jxl.
default_format: heic
default_quality: 90
overwrite_existing: false

# Every RAW file remaining in raw_dir is treated as selected and included in backup.
raw_extensions:
  - .arw
  - .cr3
  - .nef
  - .raf
  - .rw2
  - .dng

# Missing destinations warn and continue.
backup_destinations:
  - /Volumes/BackupDrive/PhotoBackups
  - /Volumes/NAS/PhotoBackups
```

- [ ] **Step 3: Run all unit tests**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 4: Verify package entrypoint**

Run:

```bash
python3 -m photo_flow --help
```

Expected: Help output containing `photo-flow`, `estimate`, and `run`.

- [ ] **Step 5: Commit**

```bash
git add README.md config.example.yaml
git commit -m "docs: document photo-flow usage"
```

---

## Self-Review

Spec coverage:

- Python CLI: covered by Tasks 1, 2, 11, and 12.
- Config file and runtime overrides: covered by Tasks 3, 11, and 12.
- TIFF conversion to HEIC/JPEG/PNG/JXL: covered by Task 6.
- Quality selection and PNG warning: covered by Tasks 6 and 12.
- Small-sample size estimation: covered by Tasks 7 and 11.
- User confirmations before conversion and TIFF cleanup: covered by Task 12.
- No RAW deletion: enforced by design and scanner/backup flow in Tasks 4 and 12.
- TIFF cleanup to Trash: covered by Task 10 and Task 12.
- Logging: covered by Task 10 and Task 12.
- Encryption prompt and `.7z`: covered by Tasks 9 and 12.
- Multi-destination backups with missing destination warnings: covered by Task 9 and Task 12.
- Integrity checks: covered by Tasks 8, 12, and 13.
- Manifest with hashes: covered by Task 9.

Placeholder scan:

- No `TBD`, `TODO`, or unspecified implementation steps remain.
- Integration tests with actual Homebrew tools are intentionally not mandatory in this plan because unit tests cover command construction and orchestration boundaries.

Type consistency:

- `OutputFormat`, `AppConfig`, `SessionInventory`, `ConversionPlan`, and `CommandResult` are introduced before use.
- CLI calls `run_command` only through an alias after adding `photo_flow.commands.run_command` to avoid a name collision with the CLI `run_command`.

---

## Execution Options

Plan complete and saved to `docs/superpowers/plans/2026-06-10-photo-workflow-automation.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
