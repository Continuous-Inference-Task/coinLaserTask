"""
generateMeanStimulus - Generates a sequence of mean values and durations
for the stimulus.
"""
import numpy as np
import matplotlib.pyplot as plt


def generate_mean_stimulus(total_seconds=300, block_design=None, samp_rate=1000):
    """
    Generate a mean stimulus sequence.

    Parameters
    ----------
    total_seconds : float
        Total duration in seconds.
    block_design : dict or None
        Block design dict. If None, uses default settings.
    samp_rate : float
        Sampling rate in Hz (used only if block_design is not None).

    Returns
    -------
    stim : dict
        Stimulus dict with meanValues, meanValuesDeg, meanDurations, time,
        meanValueVector, meanValueVectorDeg.
    """
    if block_design is None:
        # default settings
        jump_values = [-5, -3, -1, 1, 3, 5]
        STD = 20
        mean_dur = 5000
        std_dur = 1500
        min_dur = 500
        max_dur = 10000
        flag_plot = True
    else:
        # extract block design info
        jump_values = block_design['jumpValueSet']
        STD = block_design['noise']
        mean_dur = block_design['durMeanStdMinMax'][0] * samp_rate
        std_dur = block_design['durMeanStdMinMax'][1] * samp_rate
        min_dur = block_design['durMeanStdMinMax'][2] * samp_rate
        max_dur = block_design['durMeanStdMinMax'][3] * samp_rate
        flag_plot = False

    n_values = len(jump_values)

    total_length = 0
    mean_values = [0]
    durations = []
    while total_length < total_seconds * samp_rate:
        # generate a new mean
        mean_values.append(mean_values[-1] + jump_values[np.random.randint(0, n_values)] * STD)
        # generate a duration for the new mean
        new_dur = 0
        while new_dur < min_dur or new_dur > max_dur:
            new_dur = round(mean_dur + std_dur * np.random.randn())
        durations.append(new_dur)
        total_length += durations[-1]

    # Remove the initial 0
    mean_values.pop(0)

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

    if flag_plot:
        fig, ax = plt.subplots()
        ax.plot(stim['time'], stim['meanValueVector'])
        plt.show()

    return stim
