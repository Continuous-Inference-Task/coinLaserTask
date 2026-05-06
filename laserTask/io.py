import csv
from typing import List, Tuple

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
    """Construct the path to the session-level conditions CSV."""
    return (
        f"{cfg.sequence_root}"
        f"coin_baseline_{cfg.sequence_version}_order{info['order']}/"
        f"session_s{info['session']}_baseline_{cfg.sequence_version}.csv"
    )


def build_practice_session_path(cfg: ExperimentConfig, info: dict) -> str:
    """Construct the path to the practice session-level conditions CSV."""
    return (
        f"{cfg.sequence_root}"
        f"coin_practice_{cfg.practice_sequence_version}_order{info['order']}/"
        f"session_s1_practice_{cfg.practice_sequence_version}.csv"
    )


def build_save_path(cfg: ExperimentConfig, info: dict) -> str:
    """Construct the path for the custom output CSV."""
    return (
        f"{cfg.data_root}"
        f"sub-{info['participant']}"
        f"_vis-{info['visit']}"
        f"_ses-{info['session']}"
        f"_task-laser_type-baseline.csv"
    )


# Column header for the custom per-frame output file.
OUTPUT_HEADER = [
    "phase", "blockID", "currentFrame", "laserRotation", "laserDuration",
    "shieldRotation", "shieldDegrees", "shieldSizeIndex", "currentHit", "totalReward",
    "sendTrigger", "triggerValue", "shieldSizeTrigger", "trueMean", "trueVariance",
    "volatility", "stochasticity", "toneTrigger", "toneVolatility",
    "toneStochasticity",
]
