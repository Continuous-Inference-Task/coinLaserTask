import numpy as np
import pytest
from stimgen.mmn.mmn_design import mmn_design


def test_mmn_design_stable_noisy():
    d = mmn_design('stable', 0.2)
    assert d.condition == 'stable'
    assert d.dev_prob == 0.2
    assert d.tone_duration == 70
    assert d.isi_duration == 430
    assert np.array_equal(d.distances, np.array([3, 4, 4, 5, 5, 6, 6, 7]))
    assert d.max_dev_diff == 5
    assert np.array_equal(d.block_durations, np.arange(6, 11))


def test_mmn_design_volatile_precise():
    d = mmn_design('volatile', 0.1)
    assert d.condition == 'volatile'
    assert d.dev_prob == 0.1
    assert np.array_equal(d.distances, np.array([8, 9, 9, 10, 10, 11, 11, 12]))
    assert d.max_dev_diff == 3
    assert np.array_equal(d.block_durations, np.arange(3, 6))


def test_mmn_design_unsupported_prob():
    with pytest.raises(ValueError, match="Unsupported deviant probability"):
        mmn_design('stable', 0.5)
