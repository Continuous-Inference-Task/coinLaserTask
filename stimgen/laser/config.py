"""
config.py

Centralized configuration file for the CoIn (Continuous Inference) Laser Stimulus Generator.
This file contains the high-level parameters for generating the experimental sequences.
"""

import os
import sys

# ---- shared values (single source of truth) ----
# Add project root to path so we can import config_shared
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
from config_shared import SEQUENCE_VERSION, PRACTICE_SEQUENCE_VERSION, SEQUENCE_ROOT

# =============================================================================
# Global Settings
# =============================================================================
# The sampling rate for all sequences in Hz (e.g. 60 for PsychoPy/monitor refresh rate)
SAMPLE_RATE = 60

# Version strings (sourced from config_shared.py — change them there).
VERSION = SEQUENCE_VERSION
VERSION_PRACTICE = PRACTICE_SEQUENCE_VERSION

# Output directory for the generated sequences (relative to this file's location, i.e. stimgen/laser/).
# Default: '../../sequences' writes to the project-root sequences/ folder.
# You can change this to an absolute path to export elsewhere.
OUTPUT_DIR = f"../../{SEQUENCE_ROOT}"


# =============================================================================
# Experimental Parameters
# =============================================================================

# Bounds for drawing the "jump" durations per epoch.
# The laser stays in one position (epoch) for a period drawn from a
# truncated exponential distribution. These are in seconds.
JUMP_DURATION_MEAN_SEC = 0.3
JUMP_DURATION_MIN_SEC = 0.075
JUMP_DURATION_MAX_SEC = 1.0

# Base characteristics of the block conditions:
DUR_MEAN_STD_MIN_MAX_STABLE = [
    10,
    1.5,
    8,
    15,
]  # [Mean, Std, Min, Max] of epochs per block
DUR_MEAN_STD_MIN_MAX_VOLATILE = [
    3,
    1.5,
    2,
    6,
]  # [Mean, Std, Min, Max] of epochs per block

# Noise values for the observations (in degrees)
NOISE_STD_LOW = 15
NOISE_STD_HIGH = 20

# Allowed jumps for the mean position in degrees
# (When the true mean jumps, it jumps by one of these values)
JUMP_VALUE_SET = [-40, -30, -20, 20, 30, 40]


# =============================================================================
# Session Configurations
# =============================================================================
# Settings specific to different types of sessions. The durations are in minutes.

# For standard/main EEG infusion sessions and Random Walk online equivalents
MAIN_SESSION = {
    "nBlocks": 1,
    "blockDurationMin": 1,
}

# For short practice sessions (e.g. before the main task)
PRACTICE_SESSION = {
    "nBlocks": 4,
    "blockDurationMin": 2,
}

# For general testing and standard "generate_laser_session" function defaults
DEFAULT_SESSION = {"nBlocks": 12, "blockDurationMin": 3}
