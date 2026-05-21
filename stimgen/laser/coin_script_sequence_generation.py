"""
coinScriptSequenceGeneration - Main script for generating stimulus
sequences in the Laser task (CoIn / Continuous Inference study).

Generates raw laser time-series blocks for practice and main sessions,
then assembles them into counterbalanced session CSV files.

Usage:  python coin_script_sequence_generation.py
(typically called from setup.py, not directly)
"""
import os
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
    )
    n_practice_types = len(practice_design['blocks'])
    n_practice_blocks = n_practice_types * config.PRACTICE_N_SESSIONS
    practice_block_seq = _build_block_sequence(n_practice_types, n_practice_blocks)

    print(f'Practice: {n_practice_types} block type(s) × {config.PRACTICE_N_SESSIONS} session(s) = {n_practice_blocks} blocks')
    session = generate_laser_session_practice(
        practice_block_seq, practice_design, config.PRACTICE_BLOCK_DURATION_MIN
    )

    fh1, fh2 = analyse_session(session)
    session_file_name = f'practice_{config.VERSION_PRACTICE}'
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
    )
    n_main_types = len(main_design['blocks'])
    n_main_blocks = n_main_types * config.MAIN_N_SESSIONS
    main_block_seq = _build_block_sequence(n_main_types, n_main_blocks)

    print(f'\nMain: {n_main_types} block type(s) × {config.MAIN_N_SESSIONS} session(s) = {n_main_blocks} blocks')
    session = generate_laser_session(
        main_block_seq, main_design, config.MAIN_BLOCK_DURATION_MIN
    )

    fh1, fh2 = analyse_session(session)
    session_file_name = f'main_{config.VERSION}'
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
    # Session CSV files and counterbalancing
    # =========================================================================
    seq_version = config.VERSION

    # Main session CSVs
    for order_index in range(1, 5):
        generate_coin_session_csv_files(
            seq_version, order_index, 'main', output_root,
            design=main_design,
            block_sequence=main_block_seq,
            n_sessions=config.MAIN_N_SESSIONS,
            blocks_per_session=n_main_types,
        )
    print(f'\nSession CSV files generated for main ({n_main_blocks} blocks, {n_main_types}/session)')

    # Practice session CSVs
    seq_version_practice = config.VERSION_PRACTICE
    for order_index in range(1, 5):
        generate_coin_session_csv_files(
            seq_version_practice, order_index, 'practice', output_root,
            design=practice_design,
            block_sequence=practice_block_seq,
            n_sessions=config.PRACTICE_N_SESSIONS,
            blocks_per_session=n_practice_types,
        )
    print(f'Session CSV files generated for practice ({n_practice_blocks} blocks, {n_practice_types}/session)')

    print('\nAll sequences generated successfully!')


if __name__ == '__main__':
    main()
