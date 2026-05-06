"""Descriptive statistics for tone sequences.

Equivalent to ``computeSequenceStats.m``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Union

import numpy as np


def compute_sequence_stats(
    seq: Union[np.ndarray, List[int]],
    sta_dev: List[str],
) -> Dict[str, Any]:
    """Compute descriptive statistics for a PEDUKS MMN tone sequence.

    Parameters
    ----------
    seq : array-like of int
        Tone identities (``1`` = standard, ``2`` = deviant).
    sta_dev : list of str
        ``'S'`` / ``'D'`` labels, one per tone.

    Returns
    -------
    dict
        Keys:
        - ``n_deviants``, ``n_standards``, ``n_tones``, ``p_deviants``
        - ``train_length_seq`` — gap lengths between consecutive deviants.
        - ``train_lengths`` — unique train lengths.
        - ``train_length_freq`` — histogram of train lengths (all integers
          between min and max, matching MATLAB ``histcounts('integers')``).
        - ``n_reversals`` — how many deviants start a new phase.
        - ``phase_length_seq`` — gaps between reversal deviants.
        - ``phase_lengths`` — unique phase lengths.
        - ``phase_length_freq`` — histogram of phase lengths.
    """
    seq = np.asarray(seq)
    is_dev = np.array([s == "D" for s in sta_dev])

    stats: Dict[str, Any] = {
        "n_deviants": int(np.sum(is_dev)),
        "n_standards": int(np.sum([s == "S" for s in sta_dev])),
        "n_tones": int(seq.size),
        "p_deviants": (
            float(np.sum(is_dev) / seq.size) if seq.size > 0 else 0.0
        ),
    }

    # ----- train lengths (standard runs between deviants) ------------ #
    bin_seq = np.zeros(seq.shape)
    bin_seq[is_dev] = 1
    stats["train_length_seq"] = np.diff(np.where(bin_seq)[0]) - 1
    stats["train_lengths"] = np.unique(stats["train_length_seq"])
    if len(stats["train_lengths"]) > 0:
        lo = int(np.min(stats["train_lengths"]))
        hi = int(np.max(stats["train_lengths"]))
        bins = np.arange(lo, hi + 2) - 0.5
        stats["train_length_freq"], _ = np.histogram(
            stats["train_length_seq"], bins=bins
        )
    else:
        stats["train_length_freq"] = np.array([0])

    # ----- reversals ------------------------------------------------- #
    dev_idx = np.where(is_dev)[0]
    is_reversal = np.zeros(stats["n_deviants"], dtype=int)
    for i in range(stats["n_deviants"] - 1):
        if seq[dev_idx[i]] == seq[dev_idx[i] + 1]:
            is_reversal[i] = 1

    stats["n_reversals"] = int(np.sum(is_reversal))

    if stats["n_reversals"] > 0:
        stats["phase_length_seq"] = np.diff(np.where(is_reversal)[0]) - 1
        stats["phase_lengths"] = np.unique(stats["phase_length_seq"])
        if len(stats["phase_lengths"]) > 0:
            lo = int(np.min(stats["phase_lengths"]))
            hi = int(np.max(stats["phase_lengths"]))
            bins = np.arange(lo, hi + 2) - 0.5
            stats["phase_length_freq"], _ = np.histogram(
                stats["phase_length_seq"], bins=bins
            )
        else:
            stats["phase_length_freq"] = np.array([0])
    else:
        stats["phase_length_seq"] = stats["n_tones"]
        stats["phase_lengths"] = stats["n_tones"]
        stats["phase_length_freq"] = np.array([1])

    return stats
