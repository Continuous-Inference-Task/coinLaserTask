"""
coinScriptSequenceGeneration - Main script for generating stimulus
sequences in the Laser task (CoIn / Continuous Inference study).

Generates raw laser time-series blocks for practice and main sessions,
then assembles them into counterbalanced session CSV files.

MMN tone blocks are generated inline, one per main-session laser block,
with the same block duration and volatility/noise coupling.

Usage:  python coin_script_sequence_generation.py
(typically called from wizard.py, not directly)
"""
import os
import sys
import pickle
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for saving figures
import matplotlib.pyplot as plt

from generate_laser_session import generate_laser_session
from generate_laser_session_practice import generate_laser_session_practice
from design_vola_stocha import design_vola_stocha
from analyse_session import analyse_session
from plot_session import plot_session
from write_session_to_csv_file import write_session_to_csv_file
from generate_coin_session_csv_files import generate_coin_session_csv_files
import config


def _build_block_sequence(n_types, n_blocks):
    """Build a 1-based block sequence repeating all types evenly."""
    n_full = n_blocks // n_types
    n_rem = n_blocks % n_types
    seq = list(range(1, n_types + 1)) * n_full
    if n_rem > 0:
        seq.extend(list(range(1, n_rem + 1)))
    return seq


def _generate_mmn_for_main(main_design, main_block_seq, output_root, n_main_blocks):
    """Generate MMN tone blocks coupled to main-session laser blocks.

    Returns a dict mapping 1-based block index → list of MMN filenames
    (one per session-order block), plus per-block (vol, noise) indices.
    """
    # Import MMN generation (path relative to stimgen/)
    mmn_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mmn")
    sys.path.insert(0, os.path.dirname(mmn_path))
    from mmn.generate_mmn_blocks import generate_mmn_blocks

    mmn_dir = os.path.join(output_root, "mmn")

    # Build list of block type names in the order they appear
    block_types = main_design["blockTypes"]
    block_type_names = [
        block_types[main_block_seq[i] - 1]
        for i in range(n_main_blocks)
    ]

    # Build a complete deviant-probability map from actual noise presets.
    # Explicit overrides in MMN_DEVIANT_PROB_MAP are preserved.
    # Any unmapped noise preset gets 0.1 if it has the smallest σ
    # (the "precise" analogue), 0.2 otherwise.
    _noise_presets = getattr(config, "NOISE_PRESETS", {})
    _deviant_map = dict(config.MMN_DEVIANT_PROB_MAP)
    if _noise_presets:
        _min_label = min(_noise_presets.keys(), key=lambda k: _noise_presets[k])
        for _lbl in _noise_presets:
            if _lbl not in _deviant_map:
                _deviant_map[_lbl] = 0.1 if _lbl == _min_label else 0.2

    mmn_filenames = generate_mmn_blocks(
        block_types=block_type_names,
        block_duration_min=config.MAIN_BLOCK_DURATION_MIN,
        output_dir=mmn_dir,
        tone_duration_ms=config.MMN_TONE_DURATION_MS,
        isi_duration_ms=config.MMN_ISI_DURATION_MS,
        deviant_prob_map=_deviant_map,
    )

    # Build per-block (vol, noise) indices matching the MMN condition
    # Use unique vol/noise labels in design order (preserving first occurrence)
    design_block_types = main_design["blockTypes"]
    all_vol_labels = list(dict.fromkeys(vt.split("+")[0] for vt in design_block_types))
    all_noise_labels = list(dict.fromkeys(vt.split("+")[1] for vt in design_block_types))

    vol_indices = []
    noise_indices = []
    for i in range(n_main_blocks):
        bt_name = block_type_names[i]
        vol_label, noise_label = bt_name.split("+", 1)
        vol_idx = all_vol_labels.index(vol_label) if vol_label in all_vol_labels else 0
        noise_idx = all_noise_labels.index(noise_label) if noise_label in all_noise_labels else 0
        vol_indices.append(vol_idx)
        noise_indices.append(noise_idx)

    print(f'MMN tone blocks generated: {len(mmn_filenames)} blocks in {mmn_dir}')
    return mmn_filenames, vol_indices, noise_indices


def main():
    # Sort out paths and source data
    current_path = os.path.dirname(os.path.abspath(__file__))

    if os.path.isabs(config.OUTPUT_DIR):
        output_root = config.OUTPUT_DIR
    else:
        output_root = os.path.join(current_path, config.OUTPUT_DIR)

    os.makedirs(output_root, exist_ok=True)
    print(f'Saving sequences to: {output_root}\n')

    # =========================================================================
    # Practice session
    # =========================================================================
    practice_design = design_vola_stocha(
        volatility=config.PRACTICE_VOLATILITY,
        noise=config.PRACTICE_NOISE,
        noise_mode=getattr(config, "PRACTICE_NOISE_MODE", "counterbalanced"),
    )
    n_practice_types = len(practice_design['blocks'])
    n_practice_blocks = n_practice_types * config.PRACTICE_N_SESSIONS
    practice_block_seq = _build_block_sequence(n_practice_types, n_practice_blocks)

    print(f'Practice: {n_practice_types} block type(s) × {config.PRACTICE_N_SESSIONS} session(s) = {n_practice_blocks} blocks')
    session = generate_laser_session_practice(
        practice_block_seq, practice_design, config.PRACTICE_BLOCK_DURATION_MIN
    )

    fh1, fh2 = analyse_session(session)
    session_file_name = 'practice'
    write_session_to_csv_file(session, session_file_name, output_root)
    with open(os.path.join(output_root, f'session_{session_file_name}.pkl'), 'wb') as f:
        pickle.dump(session, f)
    fh1.savefig(os.path.join(output_root, f'session_{session_file_name}_move.png'), dpi=150)
    fh2.savefig(os.path.join(output_root, f'session_{session_file_name}_steps.png'), dpi=150)
    fh = plot_session(session, 0)
    fh.savefig(os.path.join(output_root, f'session_{session_file_name}_sessionPlot.png'), dpi=150)
    plt.close('all')
    print(f'Practice session saved: {session_file_name}')

    # =========================================================================
    # Main session
    # =========================================================================
    main_design = design_vola_stocha(
        volatility=config.MAIN_VOLATILITY,
        noise=config.MAIN_NOISE,
        noise_mode=getattr(config, "MAIN_NOISE_MODE", "counterbalanced"),
    )
    n_main_types = len(main_design['blocks'])
    n_main_blocks = n_main_types * config.MAIN_N_SESSIONS
    main_block_seq = _build_block_sequence(n_main_types, n_main_blocks)

    print(f'\nMain: {n_main_types} block type(s) × {config.MAIN_N_SESSIONS} session(s) = {n_main_blocks} blocks')
    session = generate_laser_session(
        main_block_seq, main_design, config.MAIN_BLOCK_DURATION_MIN
    )

    fh1, fh2 = analyse_session(session)
    session_file_name = 'main'
    write_session_to_csv_file(session, session_file_name, output_root)
    with open(os.path.join(output_root, f'session_{session_file_name}.pkl'), 'wb') as f:
        pickle.dump(session, f)
    fh1.savefig(os.path.join(output_root, f'session_{session_file_name}_move.png'), dpi=150)
    fh2.savefig(os.path.join(output_root, f'session_{session_file_name}_steps.png'), dpi=150)
    fh = plot_session(session, 0)
    fh.savefig(os.path.join(output_root, f'session_{session_file_name}_sessionPlot.png'), dpi=150)
    plt.close('all')
    print(f'Main session saved: {session_file_name}')

    # =========================================================================
    # MMN tone blocks — coupled to laser blocks (one per laser block)
    # =========================================================================
    mmn_filenames, tone_vol_list, tone_noise_list = _generate_mmn_for_main(
        main_design, main_block_seq, output_root, n_main_blocks
    )

    # =========================================================================
    # Session CSV files and counterbalancing
    # =========================================================================
    blocks_per_session = n_main_types

    # Main session CSVs (with MMN tone info)
    n_main_orders = 2 if n_main_types <= 1 else 4
    for order_index in range(1, n_main_orders + 1):
        generate_coin_session_csv_files(
            order_index, 'main', output_root,
            design=main_design,
            block_sequence=main_block_seq,
            n_sessions=config.MAIN_N_SESSIONS,
            blocks_per_session=blocks_per_session,
            mmn_filenames=mmn_filenames,
            tone_vol_list=tone_vol_list,
            tone_noise_list=tone_noise_list,
        )
    print(f'\nSession CSV files generated for main ({n_main_blocks} blocks, {blocks_per_session}/session, + MMN)')

    # Practice session CSVs (no MMN)
    n_practice_orders = 2 if n_practice_types <= 1 else 4
    for order_index in range(1, n_practice_orders + 1):
        generate_coin_session_csv_files(
            order_index, 'practice', output_root,
            design=practice_design,
            block_sequence=practice_block_seq,
            n_sessions=config.PRACTICE_N_SESSIONS,
            blocks_per_session=n_practice_types,
        )
    print(f'Session CSV files generated for practice ({n_practice_blocks} blocks, {n_practice_types}/session)')

    print('\nAll sequences generated successfully!')


if __name__ == '__main__':
    main()
