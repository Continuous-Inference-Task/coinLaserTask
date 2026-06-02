"""
config.py

Centralized configuration for the CoIn (Continuous Inference) Laser Stimulus Generator.

Block types are defined by two orthogonal dimensions:
  • Volatility — how fast the true mean jumps (controlled by epoch duration distribution)
  • Noise      — how much observation noise there is (std dev of the normal distribution)

The active block design is the Cartesian product of the selected volatility levels
and noise levels.  One session = one full set of block types (balanced across dimensions).

Usage in wizard.py:
    Choose volatility levels → choose noise levels → set sessions per task type.
    The setup wizard reads and writes this file directly.
"""

import os
import sys

# Root directory for generated sequence CSV files (relative to stimgen/laser/).
SEQUENCE_ROOT = "sequences/"

# Output directory for generated sequences (relative to stimgen/laser/).
OUTPUT_DIR = f"../../{SEQUENCE_ROOT}"


# =============================================================================
# Global Settings
# =============================================================================
SAMPLE_RATE = 60  # Hz — matches PsychoPy monitor refresh rate


# =============================================================================
# Dimension presets — these define what block types are available
# =============================================================================

# ── Volatility presets ─────────────────────────────────────────────────────
# Each preset is [mean, std, min, max] of the truncated-exponential
# distribution that controls how long the true mean stays in one position
# before jumping.  Smaller values = faster jumps = more volatile.
VOLATILITY_PRESETS = {
    "stable": [10, 1.5, 8, 15],
    "volatile": [3, 1.5, 2, 6],
    "medium": [5, 1.5, 3, 12],
}

# ── Noise presets ──────────────────────────────────────────────────────────
# Standard deviation (in degrees) of the observation noise added at each frame.
# Higher noise = laser dot scatters more around the true position.
NOISE_PRESETS = {
    "precise": 15,
    "noisy": 20,
}


# =============================================================================
# Active block designs — which presets are actually used
# =============================================================================

# ── Practice session ───────────────────────────────────────────────────────
# Usually just one block type (e.g. volatile + precise).
PRACTICE_VOLATILITY = ['stable', 'volatile']
PRACTICE_NOISE = ['noisy']
# Noise mode: "counterbalanced" = Cartesian product (volatility × noise)
#             "per_block"        = choose a specific noise level for each
#                                  volatility level (list must match in length)
PRACTICE_NOISE_MODE = 'counterbalanced'
PRACTICE_N_SESSIONS = 1
PRACTICE_BLOCK_DURATION_MIN = 1  # minutes per block

# ── Main experiment session ────────────────────────────────────────────────
MAIN_VOLATILITY = ['stable', 'volatile']
MAIN_NOISE = ['noisy']
MAIN_NOISE_MODE = 'counterbalanced'
MAIN_N_SESSIONS = 1
MAIN_BLOCK_DURATION_MIN = 4  # minutes per block


# =============================================================================
# Saved custom designs (user-created named presets)
# =============================================================================
# Each entry is a dict with "volatility", "noise", and optional "noise_mode".
# These appear in the preset picker during setup.
SAVED_DESIGNS = {
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


# =============================================================================
# MMN tone generation — coupled to laser blocks
# =============================================================================

# Tone timing (must match the values in laserTask/config.py).
MMN_TONE_DURATION_MS = 50
"""Tone length in milliseconds (standard tone for duration MMN)."""

MMN_ISI_DURATION_MS = 400
"""Inter-stimulus interval in ms (= 24 frames at 60 Hz for duration MMN)."""

# Mapping from noise-preset label to MMN deviant probability.
# "precise" blocks use fewer deviants (0.1), all others default to 0.2.
MMN_DEVIANT_PROB_MAP = {
    "precise": 0.1,
}


# ------------------------------------------------------------------ #
#  CONFIG LOADING                                                     #
# ------------------------------------------------------------------ #
# The values above are defaults.  If stimgen/laser/config.json exists
# (generated by ``python wizard.py``), its values override these defaults.
#
# ── How to configure ───────────────────────────────────────────────
#   • python wizard.py                     interactive wizard (recommended)
#   • Edit stimgen/laser/config.json directly, then re-run wizard.py
# ------------------------------------------------------------------ #

import json as _json
from pathlib import Path as _Path

_cfg_path = _Path(__file__).parent / "config.json"
if _cfg_path.is_file():
    _overlay = _json.loads(_cfg_path.read_text(encoding="utf-8"))
    for _key, _value in _overlay.items():
        if _key in globals() and not _key.startswith("_"):
            globals()[_key] = _value
