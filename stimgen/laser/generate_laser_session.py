"""
generateLaserSession - Generates an experimental session for the
continuous laser task with block-wise volatility/noise manipulation.
Task version: CoIn (Continuous Inference) study.
"""
import numpy as np
from generate_mean_jumps import generate_mean_jumps
from generate_block_stimulus import generate_block_stimulus
import config


def generate_laser_session(block_sequence, design, block_duration_min):
    """Generate a full laser session with multiple blocks.

    Parameters
    ----------
    block_sequence : list of int
        Sequence of block type indices (1-based).
    design : dict
        From design_vola_stocha() — keys 'blockTypes', 'blocks'.
    block_duration_min : int or float
        Duration of each block in minutes.

    Returns
    -------
    session : dict
        Session dict with blocks, design, settings, etc.
    """
    session = {}
    session['nBlocks'] = len(block_sequence)
    session['blockDuration'] = block_duration_min
    session['design'] = design
    session['blockSequence'] = block_sequence
    session['blockTypes'] = design['blockTypes']

    # Settings
    session['sampleRate'] = config.SAMPLE_RATE
    session['jumpDuration'] = {
        'mean': config.JUMP_DURATION_MEAN_SEC * session['sampleRate'],
        'min': config.JUMP_DURATION_MIN_SEC * session['sampleRate'],
        'max': config.JUMP_DURATION_MAX_SEC * session['sampleRate'],
    }

    session['blocks'] = []
    for i_block in range(session['nBlocks']):
        block_id = session['blockSequence'][i_block]
        block_design = design['blocks'][block_id - 1]  # 0-based indexing
        stim = generate_mean_jumps(
            session['blockDuration'] * 60,
            block_design,
            session['sampleRate']
        )
        stim = generate_block_stimulus(stim, session, block_design['noiseStd'])

        block = {
            'blockID': block_id,
            'blockType': design['blockTypes'][block_id - 1],
            'duration': session['blockDuration'] * 60,
            'stim': stim,
        }
        session['blocks'].append(block)

    return session
