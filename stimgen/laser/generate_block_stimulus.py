"""
generateBlockStimulus - Generates a continuous stimulus for a rotating laser,
where values are drawn from a normal distribution with stdev 'noise' around a
changing mean, and durations of constant epochs are drawn from an
exponential function.
"""
import numpy as np
from generate_value_vec import generate_value_vec


def generate_block_stimulus(stim, session, noise):
    """
    Generate block stimulus by filling each epoch with noisy observations.

    Parameters
    ----------
    stim : dict
        Stimulus dict (from generate_mean_jumps) with keys:
        'meanValues', 'meanDurations'.
    session : dict
        Session dict with 'jumpDuration' sub-dict containing 'mean', 'min', 'max',
        and 'sampleRate'.
    noise : float
        Standard deviation of the observation noise.

    Returns
    -------
    stim : dict
        Updated stimulus dict with added keys: 'values', 'durations',
        'valueVector', 'valuesDeg', 'valueVectorDeg', 'stdValueVectorDeg'.
    """
    stim['values'] = np.array([], dtype=float)
    stim['durations'] = []
    stim['valueVector'] = np.array([], dtype=float)

    for i_epoch in range(len(stim['meanValues'])):
        val_vec, values, n_samples_jumps = generate_value_vec(
            stim['meanDurations'][i_epoch],
            session['jumpDuration']['mean'],
            session['jumpDuration']['min'],
            session['jumpDuration']['max'],
            stim['meanValues'][i_epoch],
            noise
        )

        stim['values'] = np.concatenate([stim['values'], np.round(values)])
        stim['durations'].extend([d / session['sampleRate'] for d in n_samples_jumps])
        stim['valueVector'] = np.concatenate([stim['valueVector'], np.round(val_vec)])

    # use circle degrees for the final stimulus
    stim['valuesDeg'] = np.mod(stim['values'], 360)
    stim['valueVectorDeg'] = np.mod(stim['valueVector'], 360)

    stim['stdValueVectorDeg'] = noise * np.ones(len(stim['valueVectorDeg']))

    return stim
