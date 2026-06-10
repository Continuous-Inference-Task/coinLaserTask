"""Generate MMN tone blocks coupled to laser stimulus blocks.

Replaces the standalone ``generate_all_peduks_sessions.py`` workflow.
MMN blocks are generated inline — one per laser block — with the same
block duration as the laser task.
"""

from __future__ import annotations

import csv
import os
from typing import Any, Dict, List, Tuple

import numpy as np

from .mmn_design import mmn_design as _mmn_design_fn, MmnDesign
from .generate_block_sequence import generate_block_sequence


def generate_mmn_blocks(
    block_types: List[str],
    block_duration_min: float,
    output_dir: str,
    tone_duration_ms: int = 50,
    isi_duration_ms: int = 400,
    deviant_prob_map: Dict[str, float] | None = None,
) -> List[str]:
    """Generate one MMN tone block per laser block type instance.

    Parameters
    ----------
    block_types : list of str
        Laser block type names, e.g. ``["stable+noisy", "volatile+noisy",
        "stable+noisy", ...]``.  Each entry generates one MMN block.
    block_duration_min : float
        Block duration in **minutes** (same as laser blocks).
    output_dir : str
        Directory to write MMN block CSV files to (e.g. ``sequences/mmn``).
    tone_duration_ms : int
        Tone length in milliseconds.
    isi_duration_ms : int
        Inter-stimulus interval in milliseconds.
    deviant_prob_map : dict or None
        Mapping from noise label → deviant probability.
        Default: ``{"precise": 0.1}``, all others → 0.2.

    Returns
    -------
    list of str
        Filenames relative to ``output_dir``, one per block
        (e.g. ``["mmn_block1.csv", "mmn_block2.csv", ...]``).
    """
    if deviant_prob_map is None:
        deviant_prob_map = {"precise": 0.1}

    os.makedirs(output_dir, exist_ok=True)

    # Patch design defaults so tone timing comes from our parameters
    MmnDesign.tone_duration = tone_duration_ms
    MmnDesign.isi_duration = isi_duration_ms

    filenames: List[str] = []

    for i, block_type in enumerate(block_types, start=1):
        vol_label, noise_label = block_type.split("+", 1)

        # Determine MMN volatility and deviant probability
        mmn_condition = vol_label  # "stable" or "volatile"
        mmn_dev_prob = deviant_prob_map.get(noise_label, 0.2)

        # Generate the tone sequence
        design = _mmn_design_fn(mmn_condition, mmn_dev_prob)
        seq, sta_dev = generate_block_sequence(block_duration_min, design, plot=False)

        # Write block CSV
        filename = f"mmn_block{i}.csv"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["toneType"])
            for val in seq:
                w.writerow([int(val)])

        filenames.append(f"mmn/{filename}")

    return filenames
