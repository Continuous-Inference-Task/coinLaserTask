import os
import numpy as np
from scipy.io import loadmat

from stimgen.mmn.generate_all_peduks_sessions import generate_all_peduks_sessions


def test_generate_all_peduks_sessions(tmp_path):
    os.chdir(tmp_path)
    np.random.seed(7)
    session = generate_all_peduks_sessions()

    assert session['n_blocks'] == 12
    assert len(session['blocks']) == 12
    assert np.array_equal(
        session['block_sequence'],
        np.array([1, 2, 3, 3, 1, 2, 3, 3, 1, 2, 3, 3])
    )

    # Check file outputs
    assert os.path.isfile('mmn_session.mat')
    for i in range(1, 13):
        assert os.path.isfile(f'mmn_block{i}.csv')

    # Load mat and verify basic structure
    mat_data = loadmat('mmn_session.mat', squeeze_me=True)
    assert 'session' in mat_data
    os.chdir('/')