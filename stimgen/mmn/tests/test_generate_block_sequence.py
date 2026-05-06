import numpy as np
from stimgen.mmn.mmn_design import mmn_design
from stimgen.mmn.generate_block_sequence import generate_block_sequence


def test_generate_block_sequence_stable():
    np.random.seed(42)
    design = mmn_design('stable', 0.2)
    seq, sta_dev = generate_block_sequence(3, design, plot=False)

    assert isinstance(seq, np.ndarray)
    assert len(seq) > 0
    assert len(sta_dev) == len(seq)
    assert all(s in ('S', 'D', '') for s in sta_dev)
    assert all(s != '' for s in sta_dev)  # stable should fill all entries
    assert set(np.unique(seq)).issubset({1, 2})

    n_dev = int(np.sum(seq == 2))
    n_std = int(np.sum(seq == 1))
    assert abs(n_dev / len(seq) - 0.2) < 0.1
    assert n_std + n_dev == len(seq)


def test_generate_block_sequence_volatile():
    np.random.seed(42)
    design = mmn_design('volatile', 0.2)
    seq, sta_dev = generate_block_sequence(3, design, plot=False)

    assert isinstance(seq, np.ndarray)
    assert len(seq) > 0
    assert len(sta_dev) == len(seq)
    assert set(np.unique(seq)).issubset({1, 2})

    # Volatile sequence should still contain both tones
    assert 1 in seq and 2 in seq


def test_generate_block_sequence_length():
    np.random.seed(123)
    design = mmn_design('stable', 0.2)
    seq, _ = generate_block_sequence(3, design, plot=False)
    tone_unit = design.tone_duration + design.isi_duration
    expected = int(np.ceil(3 * 60 * 1000 / tone_unit))
    assert len(seq) == expected
