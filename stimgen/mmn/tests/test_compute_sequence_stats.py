import numpy as np
from stimgen.mmn.compute_sequence_stats import compute_sequence_stats


def test_compute_sequence_stats_basic():
    seq = np.array([1, 1, 2, 1, 1, 1, 2])
    sta_dev = ['S', 'S', 'D', 'S', 'S', 'S', 'D']
    stats = compute_sequence_stats(seq, sta_dev)

    assert stats['n_deviants'] == 2
    assert stats['n_standards'] == 5
    assert stats['n_tones'] == 7
    assert abs(stats['p_deviants'] - 2 / 7) < 1e-9

    # train_length_seq = [2, 3]
    assert np.array_equal(stats['train_length_seq'], np.array([3]))
    assert np.array_equal(stats['train_lengths'], np.array([3]))
    assert np.array_equal(stats['train_length_freq'], np.array([1]))

    assert stats['n_reversals'] == 0
    assert stats['phase_lengths'] == 7
    assert stats['phase_length_freq'][0] == 1


def test_compute_sequence_stats_one_deviant():
    seq = np.array([1, 1, 1, 2, 1, 1])
    sta_dev = ['S', 'S', 'S', 'D', 'S', 'S']
    stats = compute_sequence_stats(seq, sta_dev)
    assert stats['n_deviants'] == 1
    assert stats['train_length_freq'][0] == 0


def test_compute_sequence_stats_reversal():
    # Two consecutive deviants with the same tone value -> reversal at first of the pair
    seq = np.array([1, 2, 2, 1])
    sta_dev = ['S', 'D', 'D', 'S']
    stats = compute_sequence_stats(seq, sta_dev)

    assert stats['n_deviants'] == 2
    assert stats['n_reversals'] == 1
    assert stats['phase_length_freq'][0] == 0


def test_compute_sequence_stats_all_standards():
    seq = np.array([1, 1, 1, 1])
    sta_dev = ['S', 'S', 'S', 'S']
    stats = compute_sequence_stats(seq, sta_dev)
    assert stats['n_deviants'] == 0
    assert stats['n_standards'] == 4
    assert stats['train_length_freq'][0] == 0
