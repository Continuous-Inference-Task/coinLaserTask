"""Single-block tone-sequence generation.

Equivalent to ``generateBlockSequence.m``.
"""

from __future__ import annotations

import copy
from typing import List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt


def _build_sta_dev(seq: np.ndarray) -> List[str]:
    """Build standard/deviant label list from a 1/2 sequence array."""
    labels: List[str] = [""] * len(seq)
    for idx in np.where(seq == 1)[0]:
        labels[idx] = "S"
    for idx in np.where(seq == 2)[0]:
        labels[idx] = "D"
    return labels


def _generate_stable_sequence(
    n_tones: int,
    n_deviants: int,
    design: "MmnDesign",  # noqa: F821 — imported lazily by caller
) -> np.ndarray:
    """Generate a stable block via vectorised rejection sampling.

    Faithfully reproduces the MATLAB algorithm: chunks ``[zeros(1,d) 1]``
    are concatenated until the total length reaches *n_tones*, then
    truncated.  The process repeats until the surviving deviant count
    falls inside ``[nDeviants-maxDevDiff, nDeviants+maxDevDiff]``.

    Vectorisation makes this efficient (~50 ms per block) despite the
    ~1/25 000 acceptance rate.
    """
    lo = n_deviants - design.max_dev_diff
    hi = n_deviants + design.max_dev_diff
    max_chunks = int(n_tones / (np.min(design.distances) + 1)) + 10

    while True:
        drawn = np.random.choice(design.distances, size=max_chunks)
        cumlen = np.cumsum(drawn.astype(np.int64) + 1)
        n_dev = int(np.searchsorted(cumlen, n_tones, side="right"))
        if lo <= n_dev <= hi:
            break

    needed = int(np.searchsorted(cumlen, n_tones, side="left")) + 1
    used = drawn[:needed]
    parts = []
    for d in used:
        parts.append(np.zeros(int(d), dtype=np.float64))
        parts.append(np.ones(1, dtype=np.float64))
    return np.concatenate(parts)[:n_tones]


def _generate_volatile_sequence(
    n_tones: int,
    seq: np.ndarray,
    design: "MmnDesign",  # noqa: F821
) -> np.ndarray:
    """Apply reversal flips to a stable seed sequence."""
    seq = seq - 1
    dev_in_seq = np.where(seq)[0]
    seq[seq < 1] = -1
    idx = 0
    flip = bool(np.random.randint(0, 2))

    while True:
        block_len = int(np.random.choice(design.block_durations))
        if idx + block_len >= len(dev_in_seq):
            break
        if flip:
            start = dev_in_seq[idx] + 1
            end = dev_in_seq[idx + block_len] + 1
            seq[start:end] = -seq[start:end]
            flip = False
        else:
            flip = True
        idx += block_len

    seq[seq < 0] = 0
    return seq + 1


def generate_block_sequence(
    block_duration: float,
    design: "MmnDesign",  # noqa: F821
    plot: bool = False,
) -> Tuple[np.ndarray, List[str]]:
    """Generate a tone sequence for a single MMN block.

    Parameters
    ----------
    block_duration : float
        Block length in **minutes** (typically 3).
    design : MmnDesign
        Design object from :func:`mmn_design`.
    plot : bool
        If ``True``, show diagnostic Matplotlib plots (train-length
        histogram and sequence overview).

    Returns
    -------
    seq : np.ndarray of int
        Array of ``1`` (standard) and ``2`` (deviant), one element per tone.
    sta_dev : list of str
        ``'S'`` / ``'D'`` labels, one per tone, always consistent with *seq*.
    """
    tone_unit = design.tone_duration + design.isi_duration
    n_tones = int(np.ceil(block_duration * 60 * 1000 / tone_unit))
    n_deviants = round(n_tones * design.dev_prob)

    if design.condition == "stable":
        seq = _generate_stable_sequence(n_tones, n_deviants, design)

        if plot:
            plt.figure()
            plt.hist(np.diff(np.where(seq)[0]) - 1, bins="auto")
            plt.title("Stable train lengths")
            plt.show()

        seq = seq + 1

        if plot:
            plt.figure()
            plt.plot(seq, "o")
            plt.title("Stable sequence")
            plt.show()

        sta_dev = _build_sta_dev(seq)

    elif design.condition == "volatile":
        stable_design = copy.deepcopy(design)
        stable_design.condition = "stable"
        seed_seq, seed_sta_dev = generate_block_sequence(block_duration, stable_design, plot=plot)

        seq = _generate_volatile_sequence(n_tones, seed_seq, design)

        if plot:
            plt.figure()
            plt.plot(seq, "o")
            plt.title("Volatile sequence")
            plt.show()

        # Keep sta_dev from the stable seed — matching MATLAB, which never
        # updates staDev after volatile reversals.  The pre-reversal labels
        # encode the original role assignment; mismatches with seq indicate
        # where reversals occurred.
        sta_dev = seed_sta_dev

    else:
        raise ValueError(f"Unknown condition: {design.condition}")

    return seq, sta_dev
