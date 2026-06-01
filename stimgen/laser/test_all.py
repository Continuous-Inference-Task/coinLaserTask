"""
Comprehensive test script to validate every Python translation against
expected MATLAB behavior. Checks edge cases, array shapes, value ranges,
and internal consistency.
"""
import os
import sys

# Lock configuration variables to standard defaults for consistent unit tests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
config.MAIN_VOLATILITY = ['stable', 'volatile']
config.MAIN_NOISE = ['precise', 'noisy']
config.MAIN_NOISE_MODE = 'counterbalanced'
config.PRACTICE_VOLATILITY = ['stable', 'volatile']
config.PRACTICE_NOISE = ['precise', 'noisy']
config.PRACTICE_NOISE_MODE = 'counterbalanced'
config.NOISE_PRESETS["precise"] = 15
config.NOISE_PRESETS["noisy"] = 20
config.NOISE_PRESETS["medium"] = 10.0
config.MAIN_BLOCK_DURATION_MIN = 3
config.PRACTICE_BLOCK_DURATION_MIN = 1

import numpy as np


def test_design_vola_stocha():
    import config
    from design_vola_stocha import design_vola_stocha
    d = design_vola_stocha()
    assert len(d['blockTypes']) == 4
    assert d['blockTypes'] == ['stable+precise', 'stable+noisy', 'volatile+precise', 'volatile+noisy']
    assert len(d['blocks']) == 4
    # Check block 0 (MATLAB block 1)
    assert d['blocks'][0]['durMeanStdMinMax'] == config.VOLATILITY_PRESETS['stable']
    assert d['blocks'][0]['noiseStd'] == config.NOISE_PRESETS['precise']
    assert d['blocks'][1]['noiseStd'] == config.NOISE_PRESETS['noisy']
    assert d['blocks'][2]['durMeanStdMinMax'] == config.VOLATILITY_PRESETS['volatile']
    assert d['blocks'][3]['noiseStd'] == config.NOISE_PRESETS['noisy']
    # All blocks should have jumpValueSet
    for b in d['blocks']:
        assert b['jumpValueSet'] == config.JUMP_VALUE_SET
    print("✓ design_vola_stocha")

def test_design_vola_stocha_random_walk():
    import config
    from design_vola_stocha_random_walk import design_vola_stocha_random_walk
    d = design_vola_stocha_random_walk()
    assert len(d['blocks']) == 4
    assert d['blocks'][0]['sigmaStream'] == 1.5
    assert d['blocks'][0]['sigmaObs'] == config.NOISE_PRESETS.get('precise', 10)
    assert d['blocks'][2]['sigmaStream'] == 3
    assert d['blocks'][3]['sigmaObs'] == config.NOISE_PRESETS.get('noisy', 20)
    print("✓ design_vola_stocha_random_walk")

def test_laser_colours():
    from laser_colours import laser_colours
    col = laser_colours()
    assert len(col) == 4
    np.testing.assert_allclose(col['stablePrecise'], np.array([67, 147, 195]) / 255)
    np.testing.assert_allclose(col['volatileNoisy'], np.array([244, 165, 130]) / 255)
    print("✓ laser_colours")

def test_generate_value_vec():
    from generate_value_vec import generate_value_vec
    np.random.seed(42)
    n_frames = 100
    val_vec, values, durations = generate_value_vec(n_frames, 20, 5, 40, 50, 10)
    # val_vec length must equal n_frames
    assert len(val_vec) == n_frames, f"Expected {n_frames}, got {len(val_vec)}"
    # sum of durations must equal n_frames (after truncation)
    assert sum(durations) == n_frames, f"sum(durations)={sum(durations)} != {n_frames}"
    # number of values must equal number of durations
    assert len(values) == len(durations)
    # all durations should be positive
    assert all(d > 0 for d in durations), f"Found non-positive duration: {durations}"
    # val_vec should consist of constant segments matching values
    idx = 0
    for i, dur in enumerate(durations):
        segment = val_vec[idx:idx+dur]
        assert np.all(segment == segment[0]), f"Segment {i} not constant"
        assert segment[0] == values[i], f"Segment {i} value mismatch"
        idx += dur
    print("✓ generate_value_vec")

def test_generate_mean_jumps():
    import config
    from generate_mean_jumps import generate_mean_jumps
    from design_vola_stocha import design_vola_stocha
    np.random.seed(42)
    design = design_vola_stocha()
    block_design = design['blocks'][0]  # stablePrecise
    samp_rate = config.SAMPLE_RATE
    total_seconds = 60  # 1 minute
    stim = generate_mean_jumps(total_seconds, block_design, samp_rate)

    # meanValues and meanDurations must have same length
    assert len(stim['meanValues']) == len(stim['meanDurations']), \
        f"meanValues({len(stim['meanValues'])}) != meanDurations({len(stim['meanDurations'])})"
    # sum of durations should equal total_seconds * samp_rate
    assert sum(stim['meanDurations']) == total_seconds * samp_rate, \
        f"sum(durations)={sum(stim['meanDurations'])} != {total_seconds * samp_rate}"
    # meanValueVector length should match sum of durations
    assert len(stim['meanValueVector']) == sum(stim['meanDurations'])
    # time vector
    assert len(stim['time']) == sum(stim['meanDurations'])
    # meanValueVectorDeg should be in [0, 360)
    assert np.all(stim['meanValueVectorDeg'] >= 0)
    assert np.all(stim['meanValueVectorDeg'] < 360)
    # first mean value should be in [1, 360] (randi(360))
    assert 1 <= stim['meanValues'][0] <= 360
    # jumps should be from jumpValueSet
    jump_values = set(block_design['jumpValueSet'])
    diffs = np.diff(stim['meanValues'])
    for d in diffs:
        assert d in jump_values, f"Jump {d} not in jumpValueSet {jump_values}"
    print("✓ generate_mean_jumps")

def test_generate_block_stimulus():
    import config
    from generate_mean_jumps import generate_mean_jumps
    from generate_block_stimulus import generate_block_stimulus
    from design_vola_stocha import design_vola_stocha
    np.random.seed(42)
    design = design_vola_stocha()
    block_design = design['blocks'][0]
    samp_rate = config.SAMPLE_RATE
    session = {
        'sampleRate': samp_rate,
        'jumpDuration': {
            'mean': 0.3 * samp_rate,
            'min': 0.1 * samp_rate,
            'max': 1 * samp_rate,
        }
    }
    stim = generate_mean_jumps(60, block_design, samp_rate)
    stim = generate_block_stimulus(stim, session, block_design['noiseStd'])

    # valueVector should have same length as meanValueVector
    assert len(stim['valueVector']) == len(stim['meanValueVector']), \
        f"valueVector({len(stim['valueVector'])}) != meanValueVector({len(stim['meanValueVector'])})"
    # valueVectorDeg should be in [0, 360)
    assert np.all(stim['valueVectorDeg'] >= 0)
    assert np.all(stim['valueVectorDeg'] < 360)
    # stdValueVectorDeg should be constant = noiseStd
    assert np.all(stim['stdValueVectorDeg'] == block_design['noiseStd'])
    print("✓ generate_block_stimulus")

def test_generate_block_stimulus_random_walk():
    from generate_block_stimulus_random_walk import generate_block_stimulus_random_walk
    np.random.seed(42)
    params = {
        'Fs': 60,
        'stimDur': 30,
        'sigmaStream': 2,
        'sigmaObs': 10,
        'doJitter': 1,
        'jitter': {'mean': 18, 'min': 6, 'max': 60},
    }
    stim = generate_block_stimulus_random_walk(params)
    n_expected = int(np.ceil(60 * 30))
    assert len(stim['meanValueVector']) == n_expected, \
        f"meanValueVector length {len(stim['meanValueVector'])} != {n_expected}"
    assert len(stim['valueVector']) == n_expected
    assert len(stim['time']) == n_expected
    assert len(stim['valueVectorDeg']) == n_expected
    assert len(stim['stdValueVectorDeg']) == n_expected
    # stdValueVectorDeg should all be sigmaObs
    assert np.all(stim['stdValueVectorDeg'] == 10)
    # durations should sum to n_expected
    assert sum(stim['durations']) == n_expected, \
        f"sum(durations)={sum(stim['durations'])} != {n_expected}"
    # time should start at 1/Fs and end at n_expected/Fs
    np.testing.assert_allclose(stim['time'][0], 1/60)
    np.testing.assert_allclose(stim['time'][-1], n_expected/60)
    print("✓ generate_block_stimulus_random_walk (with jitter)")

def test_generate_block_stimulus_random_walk_no_jitter():
    from generate_block_stimulus_random_walk import generate_block_stimulus_random_walk
    np.random.seed(42)
    params = {
        'Fs': 60,
        'stimDur': 10,
        'sigmaStream': 1.5,
        'sigmaObs': 20,
        'doJitter': 0,
    }
    stim = generate_block_stimulus_random_walk(params)
    n_expected = int(np.ceil(60 * 10))
    assert len(stim['valueVector']) == n_expected
    # With no jitter, every sample should be resampled (no repeats from hold)
    # valueVector should NOT have NaN
    assert not np.any(np.isnan(stim['valueVector']))
    # durations should be empty when no jitter
    assert len(stim['durations']) == 0
    print("✓ generate_block_stimulus_random_walk (no jitter)")

def test_generate_block_stimulus_random_walk_poiss_draw():
    from generate_block_stimulus_random_walk_poiss_draw import generate_block_stimulus_random_walk_poiss_draw
    np.random.seed(42)
    # Test with poissDraw > 0
    params = {
        'Fs': 60,
        'stimDur': 10,
        'sigmaStream': 2,
        'sigmaObs': 50,
        'poissDraw': 500,  # 500ms
    }
    stim = generate_block_stimulus_random_walk_poiss_draw(params)
    n_expected = int(np.ceil(60 * 10))
    assert len(stim['valueVector']) == n_expected
    assert not np.any(np.isnan(stim['valueVector']))
    # Test with poissDraw == 0 (every sample updated)
    params2 = {'Fs': 60, 'stimDur': 5, 'sigmaStream': 1, 'sigmaObs': 10, 'poissDraw': 0}
    stim2 = generate_block_stimulus_random_walk_poiss_draw(params2)
    assert len(stim2['valueVector']) == int(np.ceil(60 * 5))
    print("✓ generate_block_stimulus_random_walk_poiss_draw")

def test_generate_laser_session():
    import config
    from generate_laser_session import generate_laser_session
    from design_vola_stocha import design_vola_stocha
    np.random.seed(42)
    design = design_vola_stocha()
    session = generate_laser_session([1, 2, 3, 4], design, config.MAIN_BLOCK_DURATION_MIN)
    assert session['nBlocks'] == 4
    assert session['blockDuration'] == config.MAIN_BLOCK_DURATION_MIN
    assert session['sampleRate'] == config.SAMPLE_RATE
    assert len(session['blocks']) == 4
    # Check block types match
    expected_types = ['stable+precise', 'stable+noisy', 'volatile+precise', 'volatile+noisy']
    for i, blk in enumerate(session['blocks']):
        assert blk['blockID'] == i + 1
        assert blk['blockType'] == expected_types[i]
        assert blk['duration'] == config.MAIN_BLOCK_DURATION_MIN * 60
        # Stim should have all required keys
        stim = blk['stim']
        for key in ['meanValues', 'meanDurations', 'meanValueVector', 'meanValueVectorDeg',
                     'values', 'valueVector', 'valueVectorDeg', 'stdValueVectorDeg', 'time']:
            assert key in stim, f"Missing key '{key}' in stim for block {i}"
        # Vector lengths should be consistent
        n = len(stim['meanValueVector'])
        assert len(stim['valueVector']) == n, f"Block {i}: valueVector len mismatch"
        assert len(stim['valueVectorDeg']) == n
        assert len(stim['time']) == n
        assert len(stim['stdValueVectorDeg']) == n
    print("✓ generate_laser_session")

def test_generate_laser_session_practice():
    import config
    from generate_laser_session_practice import generate_laser_session_practice
    from design_vola_stocha import design_vola_stocha
    np.random.seed(42)
    design = design_vola_stocha(
        volatility=config.PRACTICE_VOLATILITY,
        noise=config.PRACTICE_NOISE,
    )
    block_seq = list(range(1, len(design['blocks']) + 1))
    session = generate_laser_session_practice(block_seq, design, config.PRACTICE_BLOCK_DURATION_MIN)
    assert session['nBlocks'] == len(session['blockSequence'])
    assert session['blockDuration'] == config.PRACTICE_BLOCK_DURATION_MIN
    assert len(session['blocks']) == len(block_seq)
    # Each block should be 60 seconds
    for blk in session['blocks']:
        assert blk['duration'] == config.PRACTICE_BLOCK_DURATION_MIN * 60
    print("✓ generate_laser_session_practice")

def test_write_session_to_csv_file():
    import tempfile
    from generate_laser_session_practice import generate_laser_session_practice
    from write_session_to_csv_file import write_session_to_csv_file
    from design_vola_stocha import design_vola_stocha
    import config
    np.random.seed(42)
    design = design_vola_stocha(
        volatility=config.PRACTICE_VOLATILITY,
        noise=config.PRACTICE_NOISE,
    )
    session = generate_laser_session_practice([1], design, config.PRACTICE_BLOCK_DURATION_MIN)
    with tempfile.TemporaryDirectory() as tmpdir:
        write_session_to_csv_file(session, 'test', tmpdir)
        csv_path = os.path.join(tmpdir, 'test_block1.csv')
        assert os.path.exists(csv_path), f"CSV file not created: {csv_path}"
        with open(csv_path) as f:
            lines = f.readlines()
        # Check header
        assert lines[0].strip() == 'true_pos,obs_pos,true_var'
        # Check data rows
        n_expected = len(session['blocks'][0]['stim']['meanValueVector'])
        assert len(lines) == n_expected + 1, \
            f"Expected {n_expected + 1} lines, got {len(lines)}"
        # Check a data line has 3 integer fields
        parts = lines[1].strip().split(',')
        assert len(parts) == 3
        for p in parts:
            int(p)  # should not raise
    print("✓ write_session_to_csv_file")

def test_write_exp_csv_file():
    import tempfile
    from write_exp_csv_file import write_exp_csv_file
    from design_vola_stocha import design_vola_stocha
    design = design_vola_stocha()
    with tempfile.TemporaryDirectory() as tmpdir:
        write_exp_csv_file('test_sess', [1, 3, 2, 4], [1, 3, 2, 4],
                           ['img1.png', 'img2.png', 'img3.png', 'img4.png'],
                           design, 's1_', tmpdir)
        csv_path = os.path.join(tmpdir, 'session_s1_test_sess.csv')
        assert os.path.exists(csv_path)
        with open(csv_path) as f:
            lines = f.readlines()
        assert lines[0].strip() == 'blockID,sourceImage,volatility,stochasticity,blockFileName'
        assert len(lines) == 5  # header + 4 blocks
        # Check first data line: condList[0]=1 → cond_idx=0 → img1.png, vol=0, stoch=0
        parts = lines[1].strip().split(',')
        assert parts[0] == '1'  # blockID
        assert parts[1] == 'img1.png'
        assert parts[2] == '0'  # volatility
        assert parts[3] == '0'  # stochasticity
        # Check third line: condList[2]=2 → cond_idx=1 → img2.png, vol=0, stoch=1
        parts = lines[3].strip().split(',')
        assert parts[0] == '3'
        assert parts[1] == 'img2.png'
        assert parts[2] == '0'
        assert parts[3] == '1'
    print("✓ write_exp_csv_file")

def test_write_exp_csv_file_with_tones():
    import tempfile
    from write_exp_csv_file_with_tones import write_exp_csv_file_with_tones
    from design_vola_stocha import design_vola_stocha
    design = design_vola_stocha()
    with tempfile.TemporaryDirectory() as tmpdir:
        write_exp_csv_file_with_tones(
            'test_sess', [1, 3, 2, 4], [1, 3, 2, 4],
            ['img1.png', 'img2.png', 'img3.png', 'img4.png'],
            design, [0, 1, 0, 1], [1, 1, 0, 0], [1, 2, 3, 4],
            's1_', tmpdir
        )
        csv_path = os.path.join(tmpdir, 'session_s1_test_sess.csv')
        with open(csv_path) as f:
            lines = f.readlines()
        # Header should include tone columns
        header = lines[0].strip()
        assert 'toneVolatility' in header
        assert 'toneStochasticity' in header
        assert 'toneSeqFileName' in header
        assert len(lines) == 5
        # Check first tone: toneCondList[0]=1 → toneVola[0]=0, toneStocha[0]=1
        parts = lines[1].strip().split(',')
        assert parts[5] == '0'   # toneVolatility
        assert parts[6] == '1'   # toneStochasticity
    print("✓ write_exp_csv_file_with_tones")

def test_generate_coin_session_csv_files():
    import tempfile
    from generate_coin_session_csv_files import generate_coin_session_csv_files
    from design_vola_stocha import design_vola_stocha
    import config
    with tempfile.TemporaryDirectory() as tmpdir:
        main_design = design_vola_stocha(config.MAIN_VOLATILITY, config.MAIN_NOISE)
        main_block_seq = [1, 2, 3, 4] * 3
        # Test all task flags and all 4 orders
        for order in range(1, 5):
            generate_coin_session_csv_files('', order, 'practice', tmpdir,
                                            design=main_design, block_sequence=main_block_seq[:4],
                                            n_sessions=1, blocks_per_session=4)
            generate_coin_session_csv_files('', order, 'onlineTrain', tmpdir,
                                            design=main_design, block_sequence=main_block_seq[:4],
                                            n_sessions=1, blocks_per_session=4)
            generate_coin_session_csv_files('', order, 'main', tmpdir,
                                            design=main_design, block_sequence=main_block_seq,
                                            n_sessions=3, blocks_per_session=4)
            generate_coin_session_csv_files('', order, 'infusion', tmpdir,
                                            design=main_design, block_sequence=main_block_seq,
                                            n_sessions=3, blocks_per_session=4)
        # Verify orders 1 & 3 have same stability (stable first) vs orders 2 & 4
        # Order 1: stab_orders[0]=1, img_orders[0]=1
        # Order 2: stab_orders[1]=2, img_orders[1]=1
        o1_path = os.path.join(tmpdir, 'coin_onlineTrain_order1', 'session_s1_onlineTrain.csv')
        o2_path = os.path.join(tmpdir, 'coin_onlineTrain_order2', 'session_s1_onlineTrain.csv')
        with open(o1_path) as f:
            o1_lines = f.readlines()
        with open(o2_path) as f:
            o2_lines = f.readlines()
        # Order 1, s1: should start with stablePrecise (vol=0)
        o1_first_vol = o1_lines[1].strip().split(',')[2]
        assert o1_first_vol == '0', f"Order 1 should start stable, got vol={o1_first_vol}"
        # Order 2, s1: should start with volatilePrecise (vol=1)
        o2_first_vol = o2_lines[1].strip().split(',')[2]
        assert o2_first_vol == '1', f"Order 2 should start volatile, got vol={o2_first_vol}"
        # Check image counterbalancing: order1 vs order3
        o3_path = os.path.join(tmpdir, 'coin_onlineTrain_order3', 'session_s1_onlineTrain.csv')
        with open(o3_path) as f:
            o3_lines = f.readlines()
        o1_first_img = o1_lines[1].strip().split(',')[1]
        o3_first_img = o3_lines[1].strip().split(',')[1]
        # Order 1 uses imgAssignment1, order 3 uses imgAssignment2
        assert o1_first_img == 'radioactive1.png', f"Order 1 first img: {o1_first_img}"
        assert o3_first_img == 'radioactive4.png', f"Order 3 first img: {o3_first_img}"
    print("✓ generate_coin_session_csv_files (all orders, all task flags)")

def test_generate_mean_stimulus():
    from generate_mean_stimulus import generate_mean_stimulus
    np.random.seed(42)
    import matplotlib
    matplotlib.use('Agg')
    stim = generate_mean_stimulus(total_seconds=10)
    assert len(stim['meanValues']) == len(stim['meanDurations'])
    assert len(stim['meanValueVector']) == sum(stim['meanDurations'])
    assert len(stim['time']) == sum(stim['meanDurations'])
    print("✓ generate_mean_stimulus")

def test_analyse_session():
    from generate_laser_session_practice import generate_laser_session_practice
    from design_vola_stocha import design_vola_stocha
    from analyse_session import analyse_session
    import config
    import matplotlib
    matplotlib.use('Agg')
    np.random.seed(42)
    design = design_vola_stocha(config.PRACTICE_VOLATILITY, config.PRACTICE_NOISE)
    session = generate_laser_session_practice([1], design, config.PRACTICE_BLOCK_DURATION_MIN)
    fig1, fig2 = analyse_session(session)
    assert fig1 is not None
    assert fig2 is not None
    import matplotlib.pyplot as plt
    plt.close('all')
    print("✓ analyse_session")

def test_plot_session():
    from generate_laser_session_practice import generate_laser_session_practice
    from design_vola_stocha import design_vola_stocha
    from plot_session import plot_session
    import config
    import matplotlib
    matplotlib.use('Agg')
    np.random.seed(42)
    design = design_vola_stocha(config.PRACTICE_VOLATILITY, config.PRACTICE_NOISE)
    session = generate_laser_session_practice([1], design, config.PRACTICE_BLOCK_DURATION_MIN)
    fig = plot_session(session, 0)
    assert fig is not None
    fig_deg = plot_session(session, 1)
    assert fig_deg is not None
    import matplotlib.pyplot as plt
    plt.close('all')
    print("✓ plot_session")

if __name__ == '__main__':
    test_design_vola_stocha()
    test_design_vola_stocha_random_walk()
    test_laser_colours()
    test_generate_value_vec()
    test_generate_mean_jumps()
    test_generate_block_stimulus()
    test_generate_block_stimulus_random_walk()
    test_generate_block_stimulus_random_walk_no_jitter()
    test_generate_block_stimulus_random_walk_poiss_draw()
    test_generate_laser_session()
    test_generate_laser_session_practice()
    test_write_session_to_csv_file()
    test_write_exp_csv_file()
    test_write_exp_csv_file_with_tones()
    test_generate_coin_session_csv_files()
    test_generate_mean_stimulus()
    test_analyse_session()
    test_plot_session()
    print("\n🎉 ALL TESTS PASSED!")
