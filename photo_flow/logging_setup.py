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
