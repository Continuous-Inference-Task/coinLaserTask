"""
generateMainSessionOnlineRandomWalk - Generates a main experimental session
for the continuous laser task with block-wise volatility/noise manipulation.
Task version: CoIn (Continuous Inference) study, online (random walk).
"""
import os
import pickle
from design_vola_stocha_random_walk import design_vola_stocha_random_walk
from generate_block_stimulus_random_walk import generate_block_stimulus_random_walk
from write_session_to_csv_file import write_session_to_csv_file
import config


def generate_main_session_online_random_walk(session_file_name='test_session',
                                              block_sequence=None):
    """
    Generate a main session using random walk stimulus generation, write CSV
    and pickle output.

    Parameters
    ----------
    session_file_name : str
        Base name for the output files.
    block_sequence : list of int or None
        Sequence of block type indices (1-based). Default: [1..4]*3.

    Returns
    -------
    session : dict
        Session dict.
    """
    if block_sequence is None:
        block_sequence = list(range(1, 5)) * 3

    # Design choices
    session = {}
    session['nBlocks'] = config.MAIN_SESSION['nBlocks']
    session['blockDuration'] = config.MAIN_SESSION['blockDurationMin']
    session['design'] = design_vola_stocha_random_walk()
    session['blockSequence'] = block_sequence
    session['blockTypes'] = session['design']['blockTypes']
    session['nBlocksOfEachType'] = session['nBlocks'] / len(session['design']['blocks'])

    # Settings
    session['sampleRate'] = config.SAMPLE_RATE
    session['jumpDuration'] = {
        'mean': config.JUMP_DURATION_MEAN_SEC * session['sampleRate'],
        'min': config.JUMP_DURATION_MIN_SEC * session['sampleRate'],
        'max': config.JUMP_DURATION_MAX_SEC * session['sampleRate'],
    }

    # What stays constant over blocks
    for block_type in range(len(session['design']['blocks'])):
        session['design']['blocks'][block_type]['stimDur'] = session['blockDuration'] * 60
        session['design']['blocks'][block_type]['Fs'] = session['sampleRate']
        session['design']['blocks'][block_type]['doJitter'] = 1
        session['design']['blocks'][block_type]['jitter'] = {
            'mean': session['jumpDuration']['mean'],
            'min': session['jumpDuration']['min'],
            'max': session['jumpDuration']['max'],
        }

    session['blocks'] = []
    for i_block in range(session['nBlocks']):
        block_id = session['blockSequence'][i_block]
        stim = generate_block_stimulus_random_walk(session['design']['blocks'][block_id - 1])

        block = {
            'blockID': block_id,
            'blockType': session['blockTypes'][block_id - 1],
            'duration': session['blockDuration'] * 60,
            'stim': stim,
        }
        session['blocks'].append(block)

    # Generate csv file for psychopy task
    write_session_to_csv_file(session, session_file_name)
    with open(session_file_name + '.pkl', 'wb') as f:
        pickle.dump(session, f)

    return session
