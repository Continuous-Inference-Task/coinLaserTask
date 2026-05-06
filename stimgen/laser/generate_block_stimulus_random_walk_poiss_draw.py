"""
generateBlockStimulusRandomWalk_poissDraw - Generates a sequence of mean and
actual laser locations according to a random walk + noise with Poisson-
distributed resampling intervals.
"""
import math
import numpy as np


def generate_block_stimulus_random_walk_poiss_draw(params):
    """
    Generate stimulus via random walk with Poisson-distributed resampling.

    Parameters
    ----------
    params : dict
        Parameter dict with optional keys:
        - Fs: sampling rate in Hz (default 1000)
        - stimDur: stimulation duration in seconds (default 30)
        - sigmaStream: std of Gaussian walk per sample (default 2)
        - sigmaObs: std of observation noise (default 50)
        - xStart: initial value (default random 0..359)
        - poissDraw: Poisson lambda in ms for resampling (default 0 = every sample)

    Returns
    -------
    stim : dict
        Stimulus dict with keys: params, meanValueVector, valueVector,
        meanValueVectorDeg, valueVectorDeg, stdValueVectorDeg, durations, time.
    """
    Fs = params.get('Fs', 1000)
    stim_dur = params.get('stimDur', 30)
    x_start = params.get('xStart', np.random.randint(0, 360))
    sigma_stream = params.get('sigmaStream', 2)
    sigma_obs = params.get('sigmaObs', 50)
    poiss_draw = params.get('poissDraw', 0)

    # Store defaults back
    params.setdefault('Fs', Fs)
    params.setdefault('stimDur', stim_dur)
    params.setdefault('xStart', x_start)
    params.setdefault('sigmaStream', sigma_stream)
    params.setdefault('sigmaObs', sigma_obs)

    n_samples = math.ceil(Fs * stim_dur)
    if poiss_draw > 0:
        # transform lambda from ms to number of samples
        poiss_draw = round((poiss_draw / 1000) * Fs)

    # generate 1D stimulus stream, x
    x = np.full(n_samples, np.nan)
    x_obs = np.full(n_samples, np.nan)
    x[0] = x_start
    x_obs[0] = x[0] + np.random.randn() * sigma_obs

    poiss_d_lengths = []
    current_sample_length = 0
    if poiss_draw > 0:
        poiss_d_lengths.append(np.random.poisson(poiss_draw) + 1)
        current_sample_length = 1

    for i in range(1, n_samples):
        x[i] = x[i - 1] + np.random.randn() * sigma_stream

        if poiss_draw == 0:
            # update on every sample
            x_obs[i] = x[i] + np.random.randn() * sigma_obs
        elif current_sample_length == poiss_d_lengths[-1]:
            # time to resample
            x_obs[i] = x[i] + np.random.randn() * sigma_obs
            poiss_d_lengths.append(np.random.poisson(poiss_draw) + 1)
            current_sample_length = 1
        else:
            x_obs[i] = x_obs[i - 1]
            current_sample_length += 1

    # store outputs
    stim = {}
    stim['params'] = params
    stim['meanValueVector'] = x
    stim['valueVector'] = x_obs
    stim['meanValueVectorDeg'] = np.mod(x, 360)
    stim['valueVectorDeg'] = np.mod(x_obs, 360)
    stim['stdValueVectorDeg'] = sigma_obs * np.ones(len(stim['valueVectorDeg']))
    stim['durations'] = poiss_d_lengths
    stim['time'] = np.arange(1, n_samples + 1) / Fs

    return stim
