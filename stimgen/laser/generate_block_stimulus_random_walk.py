"""
generateBlockStimulusRandomWalk - Generates a sequence of mean and actual
laser locations according to a random walk + noise with jittered sampling.
"""
import math
import numpy as np


def generate_block_stimulus_random_walk(params):
    """
    Generate stimulus via random walk with observation noise and jittered
    resampling intervals.

    Parameters
    ----------
    params : dict
        Parameter dict with optional keys:
        - Fs: sampling rate in Hz (default 1000)
        - stimDur: stimulation duration in seconds (default 30)
        - sigmaStream: std of Gaussian walk per sample (default 2)
        - sigmaObs: std of observation noise (default 50)
        - xStart: initial value (default random 0..359)
        - doJitter: whether to use jittered resampling (default 0)
        - jitter: dict with 'mean', 'min', 'max' (in samples)

    Returns
    -------
    stim : dict
        Stimulus dict with keys: params, durations, meanValues, values,
        meanValueVector, valueVector, meanValueVectorDeg, valueVectorDeg,
        stdValueVectorDeg, time.
    """
    Fs = params.get('Fs', 1000)
    stim_dur = params.get('stimDur', 30)
    x_start = params.get('xStart', np.random.randint(0, 360))
    sigma_stream = params.get('sigmaStream', 2)
    sigma_obs = params.get('sigmaObs', 50)
    do_jitter = params.get('doJitter', 0)
    jitter = params.get('jitter', None)

    # Store defaults back into params
    params.setdefault('Fs', Fs)
    params.setdefault('stimDur', stim_dur)
    params.setdefault('xStart', x_start)
    params.setdefault('sigmaStream', sigma_stream)
    params.setdefault('sigmaObs', sigma_obs)

    n_samples = math.ceil(Fs * stim_dur)

    # generate 1D stimulus stream, x
    x = np.full(n_samples, np.nan)
    x_obs = np.full(n_samples, np.nan)
    x[0] = x_start
    x_obs[0] = x[0] + np.random.randn() * sigma_obs

    # Pre-generate jittered durations (only when jitter is used)
    durations = []
    if do_jitter and jitter is not None:
        samples = 0
        while samples < n_samples:
            # draw a new duration from exponential distribution
            new_dur = round(np.random.exponential(jitter['mean']))
            # truncate: only allow durations between min and max
            while new_dur < jitter['min'] or new_dur > jitter['max']:
                new_dur = round(np.random.exponential(jitter['mean']))
            durations.append(new_dur)
            samples += new_dur

        over_samples = samples - n_samples
        # === FIX: Correct overshoot, merge if below minimum ===
        durations[-1] = durations[-1] - over_samples
        if durations[-1] < jitter['min'] and len(durations) > 1:
            fragment = durations.pop()
            durations[-1] += fragment

        # --- OLD truncation (commented out for reference) ---
        # over_samples = samples - n_samples
        # durations[-1] = durations[-1] - over_samples

    i_dur = 0
    current_sample_length = 1
    for i in range(1, n_samples):
        x[i] = x[i - 1] + np.random.randn() * sigma_stream

        if do_jitter == 0:
            # update on every sample
            x_obs[i] = x[i] + np.random.randn() * sigma_obs
        elif current_sample_length == durations[i_dur]:
            # time to resample
            x_obs[i] = x[i] + np.random.randn() * sigma_obs
            i_dur += 1
            current_sample_length = 1
        else:
            x_obs[i] = x_obs[i - 1]
            current_sample_length += 1

    # Extract unique consecutive mean values and observed values
    mean_values_mask = np.concatenate(([True], np.diff(x) != 0))
    mean_values = x[mean_values_mask]
    values_mask = np.concatenate(([True], np.diff(x_obs) != 0))
    values = x_obs[values_mask]

    # store outputs
    stim = {}
    stim['params'] = params
    stim['durations'] = durations
    stim['meanValues'] = mean_values
    stim['values'] = values
    stim['meanValueVector'] = x
    stim['valueVector'] = x_obs
    stim['meanValueVectorDeg'] = np.mod(x, 360)
    stim['valueVectorDeg'] = np.mod(x_obs, 360)
    stim['stdValueVectorDeg'] = sigma_obs * np.ones(len(stim['valueVectorDeg']))
    stim['time'] = np.arange(1, n_samples + 1) / Fs

    return stim
