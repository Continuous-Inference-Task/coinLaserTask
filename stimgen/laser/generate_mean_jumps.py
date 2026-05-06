"""
generateMeanJumps - Generates a sequence of mean values based on the
blockDesign for a duration of totalSeconds.
"""
import numpy as np


def generate_mean_jumps(total_seconds, block_design, samp_rate):
    """
    Generate mean value jumps based on block design parameters.

    Parameters
    ----------
    total_seconds : float
        Total duration in seconds.
    block_design : dict
        Block design with keys: 'jumpValueSet', 'durMeanStdMinMax'.
    samp_rate : float
        Sampling rate in Hz.

    Returns
    -------
    stim : dict
        Stimulus dict with meanValues, meanValuesDeg, meanDurations, time,
        meanValueVector, meanValueVectorDeg.
    """
    # extract block design info
    jump_values = block_design['jumpValueSet']
    mean_dur = block_design['durMeanStdMinMax'][0] * samp_rate
    std_dur = block_design['durMeanStdMinMax'][1] * samp_rate
    min_dur = block_design['durMeanStdMinMax'][2] * samp_rate
    max_dur = block_design['durMeanStdMinMax'][3] * samp_rate

    n_values = len(jump_values)

    # Generate mean values and durations
    total_length = 0
    # start in a random location
    mean_values = [np.random.randint(1, 361)]  # randi(360) in MATLAB: 1..360
    durations = []
    while total_length < total_seconds * samp_rate:
        # generate a duration for current new mean
        new_dur = 0
        while new_dur < min_dur or new_dur > max_dur:
            new_dur = round(mean_dur + std_dur * np.random.randn())
        durations.append(new_dur)
        total_length += durations[-1]
        if total_length < total_seconds * samp_rate:
            # generate a new mean, if we still need more values
            mean_values.append(mean_values[-1] + jump_values[np.random.randint(0, n_values)])

    # remove entries beyond total seconds
    to_remove = total_length - total_seconds * samp_rate
    durations[-1] = int(durations[-1] - to_remove)

    stim = {}
    stim['meanValues'] = np.array(mean_values, dtype=float)
    stim['meanValuesDeg'] = np.mod(stim['meanValues'], 360)
    stim['meanDurations'] = durations

    # generate plottable vector
    stim['time'] = np.arange(1, sum(durations) + 1) / samp_rate
    mean_value_vector = []
    for i_epoch in range(len(durations)):
        mean_value_vector.extend([stim['meanValues'][i_epoch]] * int(durations[i_epoch]))
    stim['meanValueVector'] = np.array(mean_value_vector)
    stim['meanValueVectorDeg'] = np.mod(stim['meanValueVector'], 360)

    return stim
