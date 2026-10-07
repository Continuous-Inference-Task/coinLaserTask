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


def test_mmn_design_custom_durations():
    d = mmn_design('stable', 0.1, tone_duration=50, isi_duration=400)
    assert d.tone_duration == 50
    assert d.isi_duration == 400


def test_generate_mmn_blocks_durations(tmp_path):
    import csv
    from stimgen.mmn.generate_mmn_blocks import generate_mmn_blocks

    # Test PEDUKS timing: 50 ms tone, 400 ms ISI, 4 min -> 534 tones
    peduks_dir = tmp_path / "peduks"
    files = generate_mmn_blocks(
        block_types=['stable+precise'],
        block_duration_min=4,
        output_dir=str(peduks_dir),
        tone_duration_ms=50,
        isi_duration_ms=400,
    )
    assert len(files) == 1
    peduks_file = peduks_dir / "mmn_block1.csv"
    assert peduks_file.is_file()
    with open(peduks_file, newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["toneType"]
    assert len(rows) - 1 == 534
    assert all(int(r[0]) in {1, 2} for r in rows[1:])

    # Test SLEPS timing: 70 ms tone, 430 ms ISI, 4 min -> 480 tones
    sleps_dir = tmp_path / "sleps"
    files_s = generate_mmn_blocks(
        block_types=['volatile+noisy'],
        block_duration_min=4,
        output_dir=str(sleps_dir),
        tone_duration_ms=70,
        isi_duration_ms=430,
    )
    assert len(files_s) == 1
    sleps_file = sleps_dir / "mmn_block1.csv"
    assert sleps_file.is_file()
    with open(sleps_file, newline="") as fh:
        rows_s = list(csv.reader(fh))
    assert rows_s[0] == ["toneType"]
    assert len(rows_s) - 1 == 480
    assert all(int(r[0]) in {1, 2} for r in rows_s[1:])
