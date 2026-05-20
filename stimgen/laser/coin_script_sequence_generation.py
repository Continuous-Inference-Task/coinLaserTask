"""
coinScriptSequenceGeneration - Main script for generating stimulus
sequences in the Laser task (CoIn / Continuous Inference study).

This is the Python translation of peduksScriptSequenceGeneration.m (renamed to CoIn).
"""
import os
import pickle
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for saving figures
import matplotlib.pyplot as plt

from generate_laser_session import generate_laser_session
from generate_laser_session_practice import generate_laser_session_practice
from analyse_session import analyse_session
from plot_session import plot_session
from write_session_to_csv_file import write_session_to_csv_file
from generate_coin_session_csv_files import generate_coin_session_csv_files
import config


def main():
    # Sort out paths and source data
    current_path = os.path.dirname(os.path.abspath(__file__))
    
    # Resolve output directory
    if os.path.isabs(config.OUTPUT_DIR):
        output_root = config.OUTPUT_DIR
    else:
        output_root = os.path.join(current_path, config.OUTPUT_DIR)
        
    os.makedirs(output_root, exist_ok=True)
    print(f'Saving sequences to: {output_root}\n')

    # =========================================================================
    # Task intro & practice
    # =========================================================================
    # Create a practice/training sequence with nBlocks from config
    n_practice_blocks = config.PRACTICE_SESSION["nBlocks"]
    # Clamp to 4 block types max (only 4 block designs exist)
    n_practice_types = min(n_practice_blocks, 4)
    block_sequence = list(range(1, n_practice_types + 1))
    session = generate_laser_session_practice(block_sequence)

    # Analyse the session
    fh1, fh2 = analyse_session(session)

    # Write to file
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
    # Online training
    # =========================================================================
    # Read nBlocks from config (default: 12 → 3 repetitions of the 4 block types)
    n_main_blocks = config.MAIN_SESSION.get("nBlocks", 12)
    n_types = 4  # stablePrecise, stableNoisy, volatilePrecise, volatileNoisy
    n_full_repeats = n_main_blocks // n_types
    n_remainder = n_main_blocks % n_types
    block_sequence = list(range(1, n_types + 1)) * n_full_repeats
    if n_remainder > 0:
        block_sequence.extend(list(range(1, n_remainder + 1)))
    session = generate_laser_session(block_sequence)

    fh1, fh2 = analyse_session(session)

    session_file_name = f'onlineTrain_{config.VERSION}'
    write_session_to_csv_file(session, session_file_name, output_root)
    with open(os.path.join(output_root, f'session_{session_file_name}.pkl'), 'wb') as f:
        pickle.dump(session, f)
    fh1.savefig(os.path.join(output_root, f'session_{session_file_name}_move.png'), dpi=150)
    fh2.savefig(os.path.join(output_root, f'session_{session_file_name}_steps.png'), dpi=150)
    fh = plot_session(session, 0)
    fh.savefig(os.path.join(output_root, f'session_{session_file_name}_sessionPlot.png'), dpi=150)
    plt.close('all')
    print(f'Online training session saved: {session_file_name}')

    # =========================================================================
    # EEG baseline
    # =========================================================================
    n_base_blocks = min(n_main_blocks, 8)  # baseline uses up to 8 blocks total
    n_full_repeats = n_base_blocks // n_types
    n_remainder = n_base_blocks % n_types
    block_sequence = list(range(1, n_types + 1)) * n_full_repeats
    if n_remainder > 0:
        block_sequence.extend(list(range(1, n_remainder + 1)))
    session = generate_laser_session(block_sequence)
    fh1, fh2 = analyse_session(session)

    session_file_name = f'baseline_{config.VERSION}'
    write_session_to_csv_file(session, session_file_name, output_root)
    with open(os.path.join(output_root, f'session_{session_file_name}.pkl'), 'wb') as f:
        pickle.dump(session, f)
    fh1.savefig(os.path.join(output_root, f'session_{session_file_name}_move.png'), dpi=150)
    fh2.savefig(os.path.join(output_root, f'session_{session_file_name}_steps.png'), dpi=150)
    fh = plot_session(session, 0)
    fh.savefig(os.path.join(output_root, f'session_{session_file_name}_sessionPlot.png'), dpi=150)
    plt.close('all')
    print(f'Baseline session saved: {session_file_name}')

    # =========================================================================
    # EEG infusion (main)
    # =========================================================================
    n_full_repeats = n_main_blocks // n_types
    n_remainder = n_main_blocks % n_types
    block_sequence = list(range(1, n_types + 1)) * n_full_repeats
    if n_remainder > 0:
        block_sequence.extend(list(range(1, n_remainder + 1)))
    session = generate_laser_session(block_sequence)
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

    # Online training
    task_flag = 'onlineTrain'
    for order_index in range(1, 5):
        generate_coin_session_csv_files(seq_version, order_index, task_flag,
                                         output_root, n_blocks=n_main_blocks)
    print(f'Session CSV files generated for {task_flag}')

    # Baseline EEG
    task_flag = 'baseline'
    for order_index in range(1, 5):
        generate_coin_session_csv_files(seq_version, order_index, task_flag,
                                         output_root, n_blocks=n_base_blocks)
    print(f'Session CSV files generated for {task_flag}')

    # Infusion EEG
    task_flag = 'infusion'
    for order_index in range(1, 5):
        generate_coin_session_csv_files(seq_version, order_index, task_flag,
                                         output_root, n_blocks=n_main_blocks)
    print(f'Session CSV files generated for {task_flag}')

    # Practice (note: v3 in original script)
    task_flag = 'practice'
    seq_version_practice = config.VERSION_PRACTICE
    for order_index in range(1, 5):
        generate_coin_session_csv_files(seq_version_practice, order_index, task_flag,
                                         output_root, n_blocks=n_practice_blocks)
    print(f'Session CSV files generated for {task_flag}')

    print('\nAll sequences generated successfully!')


if __name__ == '__main__':
    main()
