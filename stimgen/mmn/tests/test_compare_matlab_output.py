"""
Integration test that compares Python outputs against original MATLAB outputs.
Since MATLAB uses its own RNG, exact sequence identity is impossible.
Instead we verify structural correctness: same file names, same number of tones,
same deviant probabilities, and correct block conditions.
"""
import os
import csv
import numpy as np
import pytest
from scipy.io import loadmat

from stimgen.mmn.generate_tone_session import generate_tone_session

MATLAB_OUTPUT_DIR = '/home/feliks/Feliksier/Feliksier/Work/Master/02/HiWi/peduks_mmn_stimgen'


def _load_csv(path):
    with open(path, newline='') as f:
        reader = csv.reader(f)
        rows = list(reader)
    assert rows[0][0] == 'toneType'
    return np.array([int(r[0]) for r in rows[1:]])


@pytest.mark.parametrize("sess_name, n_blocks", [
    ('mmn', 12),
    ('sess1', 4),
    ('sess2', 4),
    ('sess3', 4),
])
def test_csv_structure_matches_original(sess_name, n_blocks, tmp_path):
    """Ensure generated CSVs have the same shape as the original MATLAB ones."""
    os.chdir(tmp_path)
    np.random.seed(1)

    # Reconstruct the original condition vector from the original .mat file if possible,
    # or just use the known one. For this test we need the correct condition sequence.
    orig_mat_path = os.path.join(MATLAB_OUTPUT_DIR, f'{sess_name}_session.mat')
    if not os.path.isfile(orig_mat_path):
        pytest.skip(f"Original MATLAB mat file not found: {orig_mat_path}")

    orig_mat = loadmat(orig_mat_path, squeeze_me=True)
    orig_session = orig_mat['session']
    # Original session is a numpy structured array. Access fields carefully.
    block_sequence = orig_session['blockSequence'].item()
    if isinstance(block_sequence, np.ndarray):
        block_sequence = block_sequence.tolist()
    if not isinstance(block_sequence, list):
        block_sequence = [block_sequence]

    # Generate new session with same block sequence
    new_session = generate_tone_session(sess_name, block_sequence)

    for i_block in range(1, n_blocks + 1):
        orig_csv = os.path.join(MATLAB_OUTPUT_DIR, f'{sess_name}_block{i_block}.csv')
        new_csv = os.path.join(tmp_path, f'{sess_name}_block{i_block}.csv')

        assert os.path.isfile(new_csv), f"Missing generated CSV: {new_csv}"
        if not os.path.isfile(orig_csv):
            continue

        orig_seq = _load_csv(orig_csv)
        new_seq = _load_csv(new_csv)

        assert len(orig_seq) == len(new_seq), (
            f"Block {i_block} length mismatch: {len(orig_seq)} vs {len(new_seq)}"
        )

        # Both should only contain 1 and 2
        assert set(np.unique(new_seq)).issubset({1, 2})

        # Check that block length matches original
        assert len(orig_seq) == len(new_seq), (
            f"Block {i_block} length mismatch: {len(orig_seq)} vs {len(new_seq)}"
        )

        # Both should only contain 1 and 2
        assert set(np.unique(new_seq)).issubset({1, 2})

        # Check that new deviant probability is plausible for this condition
        new_p_dev = np.mean(new_seq == 2)
        cond_id = int(new_session['blocks'][i_block - 1]['cond_id'])
        if cond_id == 1:
            # Stable block: either unflipped (~0.2) or flipped (~0.8)
            assert (abs(new_p_dev - 0.2) < 0.15 or abs(new_p_dev - 0.8) < 0.15), (
                f"Block {i_block} (stable) has unexpected deviant probability: {new_p_dev}"
            )
        else:
            # Volatile block: after reversals, probability should be roughly balanced
            assert 0.3 < new_p_dev < 0.7, (
                f"Block {i_block} (volatile) has unexpected deviant probability: {new_p_dev}"
            )

    os.chdir('/')
