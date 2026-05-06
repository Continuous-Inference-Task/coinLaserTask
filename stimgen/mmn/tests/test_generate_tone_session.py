import os
import csv
import numpy as np
from scipy.io import loadmat

from stimgen.mmn.generate_tone_session import generate_tone_session, write_block_csv_files


def test_generate_tone_session(tmp_path):
    os.chdir(tmp_path)
    np.random.seed(99)
    conditions = [1, 2, 3, 3]
    session = generate_tone_session('test_sess', conditions)

    assert session['n_blocks'] == 4
    assert len(session['blocks']) == 4

    for i, block in enumerate(session['blocks']):
        assert block['cond_id'] == conditions[i]
        assert 'seq' in block
        assert 'sta_dev' in block
        assert 'seq_stats' in block
        assert len(block['seq']) == len(block['sta_dev'])
        assert set(np.unique(block['seq'])).issubset({1, 2})

    # Check .mat file
    mat_path = os.path.join(tmp_path, 'test_sess_session.mat')
    assert os.path.isfile(mat_path)
    mat_data = loadmat(mat_path, squeeze_me=True)
    assert 'session' in mat_data

    # Check CSV files
    for i in range(1, 5):
        csv_path = os.path.join(tmp_path, f'test_sess_block{i}.csv')
        assert os.path.isfile(csv_path)
        with open(csv_path, newline='') as f:
            reader = list(csv.reader(f))
            assert reader[0][0] == 'toneType'
            # All remaining rows should be 1 or 2
            for row in reader[1:]:
                assert int(row[0]) in {1, 2}

    os.chdir('/')


def test_write_block_csv_files(tmp_path):
    os.chdir(tmp_path)
    session = {
        'n_blocks': 2,
        'blocks': [
            {'seq': np.array([1, 2, 1])},
            {'seq': np.array([2, 2, 1, 1])},
        ]
    }
    write_block_csv_files(session, 'dummy')

    for i in range(1, 3):
        path = os.path.join(tmp_path, f'dummy_block{i}.csv')
        assert os.path.isfile(path)
        with open(path, newline='') as f:
            rows = list(csv.reader(f))
            assert rows[0] == ['toneType']
            assert len(rows) == 1 + len(session['blocks'][i - 1]['seq'])
    os.chdir('/')
