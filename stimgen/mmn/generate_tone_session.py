"""Multi-block session generation with counterbalancing.

Equivalent to ``generateToneSession.m``.
"""

from __future__ import annotations

import csv
import os
from typing import Any, Dict, List

import numpy as np
from scipy.io import savemat

from .mmn_design import mmn_design
from .generate_block_sequence import generate_block_sequence
from .compute_sequence_stats import compute_sequence_stats


def generate_tone_session(
    sess_name: str,
    conditions: List[int],
    output_dir: str = ".",
) -> Dict[str, Any]:
    """Generate a full MMN session with multiple blocks.

    Stable blocks (condition ``1``) have their tone assignments flipped
    every second occurrence so that standard/deviant identities are
    balanced across the session.  Volatile blocks (``2``, ``3``) are
    left unchanged.

    Writes ``{sess_name}_session.mat`` and per-block CSV files to
    *output_dir* (default: current working directory).

    Parameters
    ----------
    sess_name : str
        Base name for output files (e.g. ``"mmn"``).
    conditions : list of int
        Block-condition codes:
        ``1`` = stableNoisy, ``2`` = volatileNoisy, ``3`` = volatilePrecise.
    output_dir : str
        Directory to write output files to.

    Returns
    -------
    dict
        Session structure with keys ``n_blocks``, ``block_duration``,
        ``block_sequence``, and ``blocks`` (list of per-block dicts).
    """
    os.makedirs(output_dir, exist_ok=True)

    session: Dict[str, Any] = {
        "n_blocks": len(conditions),
        "block_duration": 3,
        "block_sequence": np.array(conditions),
        "blocks": [],
    }

    stab_noisy = mmn_design("stable", 0.2)
    vola_noisy = mmn_design("volatile", 0.2)
    vola_preci = mmn_design("volatile", 0.1)

    for cond_id in session["block_sequence"]:
        cond_id = int(cond_id)
        if cond_id == 1:
            condition = "stableNoisy"
            design = stab_noisy
        elif cond_id == 2:
            condition = "volatileNoisy"
            design = vola_noisy
        else:
            condition = "volatilePrecise"
            design = vola_preci

        seq, sta_dev = generate_block_sequence(
            session["block_duration"], design, plot=False
        )
        block = {
            "cond_id": cond_id,
            "condition": condition,
            "design": design,
            "seq": seq,
            "sta_dev": sta_dev,
            "seq_stats": compute_sequence_stats(seq, sta_dev),
        }
        session["blocks"].append(block)

    # ---- alternate flip for stable blocks every second occurrence ---- #
    # MATLAB flips seq values (1↔2) but never updates staDev.
    # The original role labels are preserved intentionally.
    do_flip = bool(np.random.randint(0, 2))
    for block in session["blocks"]:
        if block["cond_id"] != 1:
            continue
        if do_flip:
            orig = block["seq"].copy()
            flipped = orig.copy()
            flipped[orig == 1] = 2
            flipped[orig == 2] = 1
            block["seq"] = flipped
            # sta_dev is NOT updated — matches MATLAB behavior
            do_flip = False
        else:
            do_flip = True

    savemat(os.path.join(output_dir, f"{sess_name}_session.mat"), {"session": session})
    write_block_csv_files(session, sess_name, output_dir)

    return session


def write_block_csv_files(session: Dict[str, Any], sess_name: str, output_dir: str = ".") -> None:
    """Write each block's tone sequence to a CSV file.

    Creates ``{sess_name}_block1.csv``, ``{sess_name}_block2.csv``, …
    with a ``toneType`` header and one row per tone (``1`` or ``2``).

    Parameters
    ----------
    session : dict
        Session dict from :func:`generate_tone_session`.
    sess_name : str
        Base name for output files.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(session["n_blocks"]):
        path = os.path.join(output_dir, f"{sess_name}_block{i + 1}.csv")
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["toneType"])
            for val in session["blocks"][i]["seq"]:
                w.writerow([int(val)])
