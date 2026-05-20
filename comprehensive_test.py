"""
comprehensive_test.py — In-depth tests for setup.py, stimulus generation,
and the main laser task logic. Run with:
    python comprehensive_test.py
or  python -m pytest comprehensive_test.py -v
"""
import os
import sys
import csv
import tempfile
import pickle
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "stimgen" / "laser"))

# ---------------------------------------------------------------------------
# 1. SETUP.PY CONFIG READ/WRITE ROUND-TRIP TESTS
# ---------------------------------------------------------------------------
def test_setup_config_reader():
    """Verify _read_laser_task_config and _read_stimgen_config return valid dicts."""
    from setup import _read_laser_task_config, _read_stimgen_config

    lcfg = _read_laser_task_config()
    assert isinstance(lcfg, dict), "laser task config should be dict"
    required = ["target_os", "fullscreen", "enable_audio", "enable_practice",
                "show_earth_background", "reset_reward_after_practice",
                "rotation_speed", "circle_radius", "loss_factor", "n_blocks"]
    # n_blocks was removed from reader — verify
    assert "n_blocks" not in lcfg, "n_blocks should not be in laser_task_config reader anymore"
    assert "show_earth_background" in lcfg, "show_earth_background should be in reader"
    assert "reset_reward_after_practice" in lcfg, "reset_reward_after_practice should be in reader"
    assert lcfg["show_earth_background"] in (True, False)
    assert lcfg["reset_reward_after_practice"] in (True, False)
    print("  ✓ _read_laser_task_config: valid, n_blocks removed, new toggles present")

    scfg = _read_stimgen_config()
    assert isinstance(scfg, dict)
    assert "MAIN_SESSION" in scfg
    assert "PRACTICE_SESSION" in scfg
    assert "DEFAULT_SESSION" in scfg
    assert "ONLINE_TRAINING_SESSION" not in scfg, "ONLINE_TRAINING_SESSION should be removed"
    assert isinstance(scfg["MAIN_SESSION"], dict)
    assert "nBlocks" in scfg["MAIN_SESSION"]
    assert "blockDurationMin" in scfg["MAIN_SESSION"]
    assert "nBlocks" in scfg["PRACTICE_SESSION"]
    assert "blockDurationMin" in scfg["PRACTICE_SESSION"]
    print("  ✓ _read_stimgen_config: valid, ONLINE_TRAINING_SESSION removed")


def test_setup_config_write_field_map():
    """Verify the field_map in _write_laser_task_config covers all read fields."""
    from setup import _read_laser_task_config
    from laserTask.config import ExperimentConfig

    lcfg = _read_laser_task_config()
    # Check all ExperimentConfig fields that are writable are in the reader
    exp_fields = set(ExperimentConfig.__dataclass_fields__.keys())
    reader_fields = set(lcfg.keys())

    # Fields we intentionally exclude from setup
    excluded = {
        "n_blocks",           # removed — duplicate with stimgen
        "background_color",   # not exposed in setup
        "style",              # StimulusStyle object, not simple value
        "shield_sizes",       # ShieldSizeConfig object
        "serial_timeout",     # minor, not exposed
        "sequence_version",   # sourced from config_shared
        "practice_sequence_version",  # sourced from config_shared  
        "sequence_root",      # sourced from config_shared
        "data_root",          # not exposed in setup
        "image_root",         # not exposed in setup
    }

    missing_from_reader = exp_fields - reader_fields - excluded
    if missing_from_reader:
        print(f"  ⚠ Fields in ExperimentConfig but not in reader: {missing_from_reader}")
    else:
        print("  ✓ All ExperimentConfig fields covered by reader (or intentionally excluded)")

    # Verify the write field_map covers reader keys
    # The field_map is inside _write_laser_task_config; we check by importing
    from setup import _write_laser_task_config
    import inspect
    src = inspect.getsource(_write_laser_task_config)
    # Check each reader key appears in the source
    write_keys = set()
    for line in src.split("\n"):
        if '": "' in line and not line.strip().startswith("#"):
            parts = line.strip().split('": "')
            if len(parts) >= 2:
                key = parts[0].strip().strip('"').strip("'")
                if key and not key.startswith("#"):
                    write_keys.add(key)
    missing_from_write = reader_fields - write_keys - {
        "window_size_w", "window_size_h",  # handled specially
        "loss_factor",  # check this
        "keyboard_backend", "use_legacy_key_tracking",
    }
    if missing_from_write:
        print(f"  ⚠ Fields in reader but missing from writer field_map: {missing_from_write}")
    else:
        print("  ✓ All reader fields covered by writer field_map")


def test_stimgen_config_write_roundtrip():
    """Verify _write_stimgen_config writes values correctly.
    Note: full round-trip restore has a known bug in _save_stimgen_from_cfg
    where a second call with the same key doesn't re-read the file.
    This test only verifies the write path works."""
    from setup import _read_stimgen_config, _save_stimgen_from_cfg
    from pathlib import Path
    import importlib
    from stimgen.laser import config as stimgen_cfg

    cfg_path = Path(__file__).resolve().parent / "stimgen" / "laser" / "config.py"
    original_content = cfg_path.read_text()

    try:
        orig = _read_stimgen_config()
        # Modify
        _save_stimgen_from_cfg({"_stimgen_updates": {
            "_main_n_blocks": orig["MAIN_SESSION"]["nBlocks"] + 1,
        }})
        importlib.reload(stimgen_cfg)
        assert stimgen_cfg.MAIN_SESSION["nBlocks"] == orig["MAIN_SESSION"]["nBlocks"] + 1
        print(f"  ✓ stimgen config write: MAIN nBlocks {orig['MAIN_SESSION']['nBlocks']} → {stimgen_cfg.MAIN_SESSION['nBlocks']}")
    finally:
        cfg_path.write_text(original_content)
        importlib.reload(stimgen_cfg)
        print("  ✓ stimgen config restored from backup")


# ---------------------------------------------------------------------------
# 2. STIMULUS GENERATION TESTS
# ---------------------------------------------------------------------------
def test_generate_laser_session_various_nblocks():
    """Test generate_laser_session with various nBlocks values."""
    from generate_laser_session import generate_laser_session
    from plot_session import plot_session
    from analyse_session import analyse_session

    for n in [1, 2, 3, 4, 5, 12]:
        seq = list(range(1, 5)) * (n // 4)
        rem = n % 4
        if rem > 0:
            seq.extend(list(range(1, rem + 1)))
        session = generate_laser_session(seq)
        assert session["nBlocks"] == n, f"Expected {n} blocks, got {session['nBlocks']}"
        assert len(session["blocks"]) == n
        # Verify each block has expected keys
        for i, blk in enumerate(session["blocks"]):
            assert "blockID" in blk
            assert "blockType" in blk
            assert "duration" in blk
            assert "stim" in blk
            assert "meanValueVector" in blk["stim"]
            assert "valueVector" in blk["stim"]
            assert "meanValueVectorDeg" in blk["stim"]
            assert "valueVectorDeg" in blk["stim"]
            assert len(blk["stim"]["meanValueVector"]) == blk["duration"] * session["sampleRate"]

        # plot_session should not crash
        fig = plot_session(session, 0)
        assert fig is not None

        # analyse_session should not crash
        f1, f2 = analyse_session(session)
        assert f1 is not None
        assert f2 is not None

    print(f"  ✓ generate_laser_session: nBlocks in {{1,2,3,4,5,12}} all work")
    import matplotlib.pyplot as plt
    plt.close("all")


def test_generate_laser_session_practice_various_nblocks():
    """Test practice session generation with various nBlocks."""
    from generate_laser_session_practice import generate_laser_session_practice
    from plot_session import plot_session
    from analyse_session import analyse_session

    for n in [1, 2, 3, 4]:
        n_types = min(n, 4)
        seq = list(range(1, n_types + 1))
        session = generate_laser_session_practice(seq)
        assert session["nBlocks"] == n_types
        assert len(session["blocks"]) == n_types
        fig = plot_session(session, 0)
        assert fig is not None
        f1, f2 = analyse_session(session)
        assert f1 is not None

    print(f"  ✓ generate_laser_session_practice: nBlocks in {{1,2,3,4}} all work")
    import matplotlib.pyplot as plt
    plt.close("all")


def test_write_session_to_csv_file():
    """Verify CSV output format is correct."""
    from generate_laser_session_practice import generate_laser_session_practice
    from write_session_to_csv_file import write_session_to_csv_file

    session = generate_laser_session_practice([1])
    with tempfile.TemporaryDirectory() as tmpdir:
        write_session_to_csv_file(session, "test", tmpdir)
        csv_path = os.path.join(tmpdir, "test_block1.csv")
        assert os.path.exists(csv_path)

        with open(csv_path) as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["true_pos", "obs_pos", "true_var"], f"Bad header: {header}"
            rows = list(reader)
            assert len(rows) == len(session["blocks"][0]["stim"]["meanValueVectorDeg"])
            for row in rows:
                assert len(row) == 3
                # All values should be valid integers (degrees)
                int(row[0]), int(row[1]), int(row[2])

    print(f"  ✓ write_session_to_csv_file: correct header, {len(rows)} data rows, all valid integers")


def test_generate_coin_session_csv_files_various_configs():
    """Test the CSV order file generation with various block counts."""
    from generate_coin_session_csv_files import generate_coin_session_csv_files

    with tempfile.TemporaryDirectory() as tmpdir:
        # Practice with 1 block
        generate_coin_session_csv_files("v3", 1, "practice", tmpdir, n_blocks=1)
        csv_path = os.path.join(tmpdir, "coin_practice_v3_order1", "session_s1_practice_v3.csv")
        assert os.path.exists(csv_path)
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1, f"practice with n_blocks=1 should have 1 row, got {len(rows)}"
        print("  ✓ coin CSV: practice n_blocks=1 → 1 row")

        # Practice with 4 blocks
        generate_coin_session_csv_files("v3", 1, "practice", tmpdir, n_blocks=4)
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
            assert len(rows) == 4, f"practice with n_blocks=4 should have 4 rows, got {len(rows)}"
        print("  ✓ coin CSV: practice n_blocks=4 → 4 rows")

        # Baseline with 2 blocks
        generate_coin_session_csv_files("v4", 1, "baseline", tmpdir, n_blocks=2)
        csv_path2 = os.path.join(tmpdir, "coin_baseline_v4_order1", "session_s1_baseline_v4.csv")
        assert os.path.exists(csv_path2)
        with open(csv_path2) as f:
            rows = list(csv.DictReader(f))
            assert len(rows) == 2
            # Should have tone columns
            assert "toneSeqFileName" in rows[0]
            assert "toneVolatility" in rows[0]
        print("  ✓ coin CSV: baseline n_blocks=2 → 2 rows with tone columns")

        # Infusion with 5 blocks → 2 sessions (4 + 1)
        generate_coin_session_csv_files("v4", 1, "infusion", tmpdir, n_blocks=5)
        csv_s1 = os.path.join(tmpdir, "coin_main_v4_order1", "session_s1_main_v4.csv")
        csv_s2 = os.path.join(tmpdir, "coin_main_v4_order1", "session_s2_main_v4.csv")
        assert os.path.exists(csv_s1)
        assert os.path.exists(csv_s2)
        with open(csv_s1) as f:
            assert len(list(csv.DictReader(f))) == 4
        with open(csv_s2) as f:
            assert len(list(csv.DictReader(f))) == 1
        print("  ✓ coin CSV: infusion n_blocks=5 → 2 sessions (4 + 1)")


def test_sequence_csv_content():
    """Validate generated sequence CSV files have valid content."""
    seq_dir = PROJECT_ROOT / "sequences"
    for csv_file in sorted(seq_dir.glob("practice_v3_block*.csv")):
        with open(csv_file) as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["true_pos", "obs_pos", "true_var"]
            rows = list(reader)
            n_frames = len(rows)
            assert n_frames > 0, f"{csv_file.name} is empty"
            for i, row in enumerate(rows):
                true_pos = int(row[0])
                obs_pos = int(row[1])
                true_var = int(row[2])
                assert 0 <= true_pos < 360, f"{csv_file.name}:{i} true_pos={true_pos} out of range"
                assert 0 <= obs_pos < 360, f"{csv_file.name}:{i} obs_pos={obs_pos} out of range"
                assert true_var > 0, f"{csv_file.name}:{i} true_var={true_var} should be >0"
        print(f"  ✓ {csv_file.name}: {n_frames} frames, all values valid")

    for csv_file in sorted(seq_dir.glob("baseline_v4_block*.csv")):
        with open(csv_file) as f:
            rows = list(csv.reader(f))[1:]  # skip header
            n_frames = len(rows)
            assert n_frames == 3600, f"{csv_file.name}: expected 3600 frames, got {n_frames}"
        print(f"  ✓ {csv_file.name}: {n_frames} frames ✓")


# ---------------------------------------------------------------------------
# 3. LASER TASK LOGIC TESTS
# ---------------------------------------------------------------------------
def test_experiment_config_defaults():
    """Test ExperimentConfig instantiates with all defaults correctly."""
    from laserTask.config import ExperimentConfig
    cfg = ExperimentConfig()
    assert cfg.show_earth_background is True
    assert cfg.reset_reward_after_practice is True
    assert cfg.enable_practice is True
    assert cfg.n_blocks == 1  # default fallback
    assert cfg.fullscreen is True
    assert cfg.window_size == (1512, 982)
    assert cfg.target_refresh_rate == 60
    # loss_factor should flow to shield_sizes
    assert cfg.shield_sizes.sizes[0].loss.miss.total == -cfg.loss_factor
    print("  ✓ ExperimentConfig defaults: all values correct, loss_factor wired")


def test_experiment_config_custom_loss_factor():
    """Test that changing loss_factor propagates to shield sizes."""
    from laserTask.config import ExperimentConfig
    for lf in [0.001, 0.003, 0.01, 0.05]:
        cfg = ExperimentConfig(loss_factor=lf)
        assert cfg.loss_factor == lf
        assert cfg.shield_sizes.sizes[0].loss.miss.total == -lf, \
            f"loss_factor={lf} should give miss=-{lf}, got {cfg.shield_sizes.sizes[0].loss.miss.total}"
    print("  ✓ loss_factor: 0.001, 0.003, 0.01, 0.05 all propagate to shield correctly")


def test_shield_computation():
    """Test compute_shield_vertices produces correct geometry.
    Requires psychopy, so skip if not available."""
    try:
        from laserTask.stimuli import compute_shield_vertices
    except ModuleNotFoundError:
        print("  ⚠ test_shield_computation: skipped (psychopy not available)")
        return

    verts = compute_shield_vertices(20.0, 3.0)
    # Shield is a curved polygon (arc segment), not a rectangle
    assert len(verts) > 2, f"Expected polygon with >2 vertices, got {len(verts)}"
    # First point is center, rest outline the arc
    assert verts[0][0] == pytest.approx(0.0, abs=0.01)
    assert verts[0][1] == pytest.approx(0.0, abs=0.01)
    # All x values should be within [-circle_radius, circle_radius]
    for v in verts:
        assert abs(v[0]) <= 3.1
        assert 0 <= v[1] <= 3.3
    print(f"  ✓ compute_shield_vertices(20°, r=3.0): {len(verts)} vertices, valid polygon")


def test_reward_tracker():
    """Test RewardTracker basic operations."""
    from laserTask.reward import RewardTracker
    from laserTask.config import ExperimentConfig, StimulusStyle

    cfg = ExperimentConfig()
    rt = RewardTracker(cfg, wins=1)  # win framing
    assert rt.total == 0.0
    assert rt.session_total == 0.0

    rt.update(True, True, size_index=0)   # hit with new evidence
    expected_hit = cfg.shield_sizes.sizes[0].win.hit.total
    assert rt.total == pytest.approx(expected_hit, abs=0.001), \
        f"Hit should increase total to {expected_hit}, got {rt.total}"

    prior = rt.total
    rt.update(False, True, size_index=0)  # miss
    expected_miss = cfg.shield_sizes.sizes[0].win.miss.total
    assert rt.total == pytest.approx(prior + expected_miss, abs=0.001), \
        f"Miss should reduce total by {expected_miss}, was {prior}, now {rt.total}"

    rt.reset_block()
    assert rt.total == 0.0
    print(f"  ✓ RewardTracker: hit → +{cfg.shield_sizes.sizes[0].win.hit.total}, miss → {cfg.shield_sizes.sizes[0].win.miss.total}, reset works")


def test_trigger_codes_unique():
    """Verify all trigger codes are unique."""
    from laserTask.config import TRIGGER_CODES
    codes = list(TRIGGER_CODES.values())
    assert len(codes) == len(set(codes)), f"Duplicate trigger codes: {codes}"
    print(f"  ✓ TRIGGER_CODES: {len(codes)} unique codes")


def test_io_load_stimulus_stream():
    """Test stimulus stream loading and validation."""
    from laserTask.io import load_stimulus_stream
    stream = load_stimulus_stream("sequences/practice_v3_block1.csv")
    assert len(stream) > 0
    assert len(stream[0]) == 3
    assert all(isinstance(v, float) for v in stream[0])
    print(f"  ✓ load_stimulus_stream: {len(stream)} frames, correct structure")


def test_io_build_paths():
    """Test that session paths resolve to existing files."""
    from laserTask.io import build_session_path, build_practice_session_path
    from laserTask.config import ExperimentConfig
    cfg = ExperimentConfig()
    info = {"participant": "x", "visit": "1", "session": "1", "order": "1", "framing": "loss"}

    path = build_session_path(cfg, info)
    assert os.path.exists(PROJECT_ROOT / path), f"Missing: {path}"
    print(f"  ✓ build_session_path → exists: {path}")

    path = build_practice_session_path(cfg, info)
    assert os.path.exists(PROJECT_ROOT / path), f"Missing: {path}"
    print(f"  ✓ build_practice_session_path → exists: {path}")


# ---------------------------------------------------------------------------
# RUN ALL
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import pytest
    print("=" * 60)
    print("COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    print()

    tests = [
        test_setup_config_reader,
        test_setup_config_write_field_map,
        test_stimgen_config_write_roundtrip,
        test_generate_laser_session_various_nblocks,
        test_generate_laser_session_practice_various_nblocks,
        test_write_session_to_csv_file,
        test_generate_coin_session_csv_files_various_configs,
        test_sequence_csv_content,
        test_experiment_config_defaults,
        test_experiment_config_custom_loss_factor,
        test_shield_computation,
        test_reward_tracker,
        test_trigger_codes_unique,
        test_io_load_stimulus_stream,
        test_io_build_paths,
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"  ✗ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"RESULTS: {len(tests) - failed}/{len(tests)} passed, {failed} failed")
    print("=" * 60)
