"""
generateValueVec - Generates a vector of values by drawing values from a
normal distribution and drawing the durations of each value from a
truncated exponential function.
"""
import numpy as np


def generate_value_vec(n_frames, mean_dur, min_dur, max_dur, mean_val, sd_val):
    """
    Generate a value vector with truncated-exponential durations and
    normally-distributed values.

    Parameters
    ----------
    n_frames : int
        Total number of frames (length of vector) to fill.
    mean_dur : float
        Mean duration for exponential function.
    min_dur : float
        Minimum duration for truncating exp function.
    max_dur : float
        Maximum duration for truncating exp function.
    mean_val : float
        Mean value for normal distribution.
    sd_val : float
        Standard deviation for normal distribution.

    Returns
    -------
    val_vec : np.ndarray
        Vector of values (length n_frames).
    values : np.ndarray
        Array of drawn values per epoch.
    durations : list
        List of durations per epoch.
    """
    # === Draw durations from exponential distribution
    frames = 0
    durations = []
    while frames < n_frames:
        # draw a new duration
        new_dur = round(np.random.exponential(mean_dur))
        # truncate: only allow durations between min_dur and max_dur
        while new_dur < min_dur or new_dur > max_dur:
            new_dur = round(np.random.exponential(mean_dur))
        durations.append(new_dur)
        # count how many frames we've covered
        frames += durations[-1]

    # === FIX: Correct overshoot in durations BEFORE painting ===
    # The while loop above overshoots n_frames. Trim the last duration
    # to fit exactly, then merge it backward if it fell below min_dur.
    overshoot = sum(durations) - n_frames
    durations[-1] = durations[-1] - overshoot
    if durations[-1] < min_dur and len(durations) > 1:
        fragment = durations.pop()      # remove the too-short tail
        durations[-1] += fragment       # absorb its frames into predecessor

    # --- OLD truncation (commented out, moved here for reference) ---
    # # discard all values after last frame
    # val_vec = val_vec[:n_frames]
    # durations[-1] = durations[-1] - (sum(durations) - n_frames)

    dur_count = len(durations)

    # === Draw coherence values from normal distribution
    val_vec = np.zeros(sum(durations))
    values = np.full(dur_count, np.nan)
    period_start = 0
    for i_epoch in range(dur_count):
        # draw a new value
        new_value = sd_val * np.random.randn() + mean_val
        # save in values
        values[i_epoch] = new_value
        # fill all frames belonging to this period with this value
        val_vec[period_start: period_start + durations[i_epoch]] = new_value
        # start time of next period
        period_start += durations[i_epoch]

    return val_vec, values, durations
