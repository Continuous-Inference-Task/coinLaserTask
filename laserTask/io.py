import csv
import os
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from laserTask.config import ExperimentConfig


def load_stimulus_stream(
    filepath: str,
) -> List[Tuple[float, float, float]]:
    """Load a block's pre-generated stimulus stream from CSV.

    Expected columns: ``trueMean, laserRotation, trueVariance``
    (header row is skipped automatically).
    """
    stream: list = []
    with open(filepath, "r") as fh:
        reader = csv.reader(fh)
        next(reader)  # skip header
        for row in reader:
            stream.append((float(row[0]), float(row[1]), float(row[2])))
    return stream


def build_session_path(cfg: ExperimentConfig, info: dict) -> str:
    """Construct the path to the main session-level conditions CSV."""
    order = info.get("order") or (cfg.orders[0] if cfg.orders else "1")
    session = info.get("session") or (cfg.sessions[0] if cfg.sessions else "1")
    return (
        f"{cfg.sequence_root}"
        f"coin_main_{cfg.sequence_version}_order{order}/"
        f"session_s{session}_main_{cfg.sequence_version}.csv"
    )


def build_practice_session_path(cfg: ExperimentConfig, info: dict) -> str:
    """Construct the path to the practice session-level conditions CSV."""
    order = info.get("order") or (cfg.orders[0] if cfg.orders else "1")
    return (
        f"{cfg.sequence_root}"
        f"coin_practice_{cfg.practice_sequence_version}_order{order}/"
        f"session_s1_practice_{cfg.practice_sequence_version}.csv"
    )


def build_save_path(cfg: ExperimentConfig, info: dict) -> str:
    """Construct the path for the custom output CSV."""
    visit = info.get("visit") or (cfg.visits[0] if cfg.visits else "1")
    session = info.get("session") or (cfg.sessions[0] if cfg.sessions else "1")
    return (
        f"{cfg.data_root}"
        f"sub-{info['participant']}"
        f"_vis-{visit}"
        f"_ses-{session}"
        f"_task-laser_type-main.csv"
    )


# Column header for the custom per-frame output file.
OUTPUT_HEADER = [
    "phase", "blockID", "currentFrame", "laserRotation", "laserDuration",
    "shieldRotation", "shieldDegrees", "shieldSizeIndex", "currentHit", "totalReward",
    "sendTrigger", "triggerValue", "shieldSizeTrigger", "trueMean", "trueVariance",
    "volatility", "stochasticity", "toneTrigger", "toneVolatility",
    "toneStochasticity",
]


def validate_dialog_options(
    cfg: ExperimentConfig, project_root: Optional[Path] = None
) -> List[str]:
    """Check that config dialog options match available sequence files.

    Scans ``sequences/`` for actual order directories and session CSVs,
    then compares against the session/order dropdown options in *cfg*.

    Returns a list of human-readable warnings (empty if everything matches).
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent

    seq_dir = project_root / cfg.sequence_root
    warnings: List[str] = []

    if not seq_dir.is_dir():
        warnings.append(
            f"Sequence directory not found: {seq_dir}. "
            "Run 'python setup.py --generate' first."
        )
        return warnings

    # ── detect available orders from filesystem ──
    # Look at main session order dirs as the canonical source
    main_dirs = sorted([
        d for d in seq_dir.iterdir()
        if d.is_dir() and d.name.startswith("coin_main_")
    ])
    if not main_dirs:
        warnings.append(
            "No main session sequence order directories found. "
            "Run 'python setup.py --generate' first."
        )
        return warnings

    available_orders: List[str] = []
    for d in main_dirs:
        # Extract order number from "coin_main_v4_order1"
        parts = d.name.rsplit("order", 1)
        if len(parts) == 2:
            available_orders.append(parts[1])

    # ── detect available sessions from first order dir ──
    first_dir = main_dirs[0]
    session_files = sorted(first_dir.glob("session_s*_main_*.csv"))
    # Extract session number from "session_s1_main_v4.csv"
    available_sessions: List[str] = []
    for sf in session_files:
        name = sf.stem  # e.g. "session_s1_main_v4"
        if name.startswith("session_s"):
            rest = name[len("session_s"):]
            sess_num = rest.split("_")[0]
            available_sessions.append(sess_num)

    # ── compare against config ──
    config_sessions = [str(s) for s in cfg.sessions]
    config_orders = [str(o) for o in cfg.orders]

    if available_sessions and config_sessions != available_sessions:
        warnings.append(
            f"Config sessions ({', '.join(config_sessions)}) "
            f"don't match generated files ({', '.join(available_sessions)}). "
            "Re-run setup to auto-sync."
        )

    if available_orders and config_orders != available_orders:
        warnings.append(
            f"Config orders ({', '.join(config_orders)}) "
            f"don't match generated files ({', '.join(available_orders)}). "
            "Re-run setup to auto-sync."
        )

    return warnings
