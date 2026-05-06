"""Design configuration for PEDUKS MMN blocks.

Equivalent to ``mmnDesign.m``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class MmnDesign:
    """Parameters defining a single MMN block design.

    Attributes
    ----------
    tone_duration : int
        Tone length in milliseconds (default 70).
    isi_duration : int
        Inter-stimulus interval in milliseconds (default 430).
    condition : str
        ``"stable"`` or ``"volatile"``.
    dev_prob : float
        Target deviant probability (0.1 or 0.2).
    distances : np.ndarray
        Chunk-length distances used during sequence generation.
    max_dev_diff : int
        Half-width of the deviant-count acceptance window
        (deviants must fall in ``[nDeviants-maxDevDiff, nDeviants+maxDevDiff]``).
    block_durations : np.ndarray
        Possible reversal-segment lengths for volatile blocks (in deviant-count units).
    """

    tone_duration: int = 70
    isi_duration: int = 430
    condition: str = ""
    dev_prob: float = 0.0
    distances: np.ndarray = field(default_factory=lambda: np.array([]))
    max_dev_diff: int = 0
    block_durations: np.ndarray = field(default_factory=lambda: np.array([]))


def mmn_design(condition: str, deviant_probability: float) -> MmnDesign:
    """Create a design configuration for a PEDUKS MMN block.

    Parameters
    ----------
    condition : str
        ``"stable"`` — standard/deviant roles are fixed.
        ``"volatile"`` — roles reverse at random intervals.
    deviant_probability : float
        Target proportion of deviants.  Must be ``0.1`` or ``0.2``.

    Returns
    -------
    MmnDesign
        Populated design object.

    Raises
    ------
    ValueError
        If *deviant_probability* is not ``0.1`` or ``0.2``.
    """
    design = MmnDesign(
        condition=condition,
        dev_prob=deviant_probability,
    )

    if design.dev_prob == 0.2:
        design.distances = np.array([3, 4, 4, 5, 5, 6, 6, 7])
        design.max_dev_diff = 5
        design.block_durations = np.arange(6, 11)
    elif design.dev_prob == 0.1:
        design.distances = np.array([8, 9, 9, 10, 10, 11, 11, 12])
        design.max_dev_diff = 3
        design.block_durations = np.arange(3, 6)
    else:
        raise ValueError(f"Unsupported deviant probability: {design.dev_prob}")

    return design
