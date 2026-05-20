"""
generateLaserSession - Generates an experimental session for the
continuous laser task with block-wise volatility/noise manipulation.
Task version: CoIn (Continuous Inference) study.
"""
import numpy as np
from design_vola_stocha import design_vola_stocha
from generate_mean_jumps import generate_mean_jumps
from generate_block_stimulus import generate_block_stimulus
import config


def generate_laser_session(block_sequence=None):
    """
    Generate a full laser session with multiple blocks.

    Parameters
    ----------
    block_sequence : list of int or None
        Sequence of block type indices (1-based, as in MATLAB).
        Default: [1,2,3,4, 1,2,3,4, 1,2,3,4].

    Returns
    -------
    session : dict
        Session dict with blocks, design, settings, etc.
    """
    if block_sequence is None:
        block_sequence = list(range(1, 5)) * 3  # [1,2,3,4,1,2,3,4,1,2,3,4]

    # Design choices
    session = {}
    session['nBlocks'] = len(block_sequence)
    session['blockDuration'] = config.MAIN_SESSION['blockDurationMin']
    session['design'] = design_vola_stocha()
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

    session['blocks'] = []
    for i_block in range(session['nBlocks']):
        # Generate block stimulus with noise
        block_id = session['blockSequence'][i_block]
        block_design = session['design']['blocks'][block_id - 1]  # 0-based indexing
        stim = generate_mean_jumps(
            session['blockDuration'] * 60,
            block_design,
            session['sampleRate']
        )
        stim = generate_block_stimulus(stim, session, block_design['noiseStd'])

        # Fill the block with stimulus and info
        block = {
            'blockID': block_id,
            'blockType': session['blockTypes'][block_id - 1],
            'duration': session['blockDuration'] * 60,
            'stim': stim,
        }
        session['blocks'].append(block)

    return session
