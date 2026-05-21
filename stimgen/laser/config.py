"""
config.py

Centralized configuration for the CoIn (Continuous Inference) Laser Stimulus Generator.

Block types are defined by two orthogonal dimensions:
  • Volatility — how fast the true mean jumps (controlled by epoch duration distribution)
  • Noise      — how much observation noise there is (std dev of the normal distribution)

The active block design is the Cartesian product of the selected volatility levels
and noise levels.  One session = one full set of block types (balanced across dimensions).

Usage in setup.py:
    Choose volatility levels → choose noise levels → set sessions per task type.
    The setup wizard reads and writes this file directly.
"""

import os
import sys

# ---- shared values (single source of truth) ----
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
from config_shared import SEQUENCE_VERSION, PRACTICE_SEQUENCE_VERSION, SEQUENCE_ROOT


# =============================================================================
# Global Settings
# =============================================================================
SAMPLE_RATE = 60  # Hz — matches PsychoPy monitor refresh rate

# Version strings (sourced from config_shared.py — change them there).
VERSION = SEQUENCE_VERSION
VERSION_PRACTICE = PRACTICE_SEQUENCE_VERSION

# Output directory for generated sequences (relative to stimgen/laser/).
OUTPUT_DIR = f"../../{SEQUENCE_ROOT}"


# =============================================================================
# Dimension presets — these define what block types are available
# =============================================================================

# ── Volatility presets ─────────────────────────────────────────────────────
# Each preset is [mean, std, min, max] of the truncated-exponential
# distribution that controls how long the true mean stays in one position
# before jumping.  Smaller values = faster jumps = more volatile.
VOLATILITY_PRESETS = {
    # CoIn / PEDUKS standard levels
    "stable":   [10, 1.5, 8, 15],
    # ^ slow changes — epochs last ~10 s on average
    "volatile": [3, 1.5, 2, 6],
    # ^ fast changes — epochs last ~3 s on average

    # CogPsy intermediate level (also available)
    "medium":   [5, 1.5, 3, 12],
    # ^ between stable and volatile
}

# ── Noise presets ──────────────────────────────────────────────────────────
# Standard deviation (in degrees) of the observation noise added at each frame.
# Higher noise = laser dot scatters more around the true position.
NOISE_PRESETS = {
    # CoIn / PEDUKS standard levels
    "precise": 15,
    # ^ observations cluster tightly around the true mean (±15°)
    "noisy":   20,
    # ^ observations scatter more (±20°)
}


# =============================================================================
# Active block designs — which presets are actually used
# =============================================================================

# ── Practice session ───────────────────────────────────────────────────────
# Usually just one block type (e.g. volatile + precise).
PRACTICE_VOLATILITY = ["volatile"]
PRACTICE_NOISE = ["precise"]
# Noise mode: "counterbalanced" = Cartesian product (volatility × noise)
#             "per_block"        = choose a specific noise level for each
#                                  volatility level (list must match in length)
PRACTICE_NOISE_MODE = "counterbalanced"
PRACTICE_N_SESSIONS = 1
PRACTICE_BLOCK_DURATION_MIN = 1  # minutes per block

# ── Main experiment session ────────────────────────────────────────────────
MAIN_VOLATILITY = ["stable", "volatile"]
MAIN_NOISE = ["precise", "noisy"]
MAIN_NOISE_MODE = "counterbalanced"
MAIN_N_SESSIONS = 3
MAIN_BLOCK_DURATION_MIN = 3  # minutes per block


# =============================================================================
# Saved custom designs (user-created named presets)
# =============================================================================
# Each entry is a dict with "volatility", "noise", and optional "noise_mode".
# These appear in the preset picker during setup.
SAVED_DESIGNS = {
    # Example:
    # "cogpsy_style": {
    #     "volatility": ["stable", "volatile"],
    #     "noise": ["precise"],
    #     "noise_mode": "counterbalanced",
    # },
}


# =============================================================================
# Common parameters (shared across all block types)
# =============================================================================

# Bounds for drawing the "jump" durations per epoch.
# The laser stays in one position for a period drawn from a truncated
# exponential distribution.
JUMP_DURATION_MEAN_SEC = 0.3
JUMP_DURATION_MIN_SEC = 0.075
JUMP_DURATION_MAX_SEC = 1.0

# Allowed jump sizes for the true mean position (degrees).
# When the true mean jumps, it changes by one of these values.
JUMP_VALUE_SET = [-40, -30, -20, 20, 30, 40]
