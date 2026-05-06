"""
plotSession - Creates subplots for the mean and actual stimulus in each
block of a session.
"""
import numpy as np
import matplotlib.pyplot as plt


def plot_session(session, flag_degrees):
    """
    Plot stimulus traces for each block in a session.

    Parameters
    ----------
    session : dict
        Session dict with 'nBlocks', 'blocks', 'design'.
    flag_degrees : bool or int
        If truthy, plot in degrees (mod 360). Otherwise, plot raw values.

    Returns
    -------
    fig : matplotlib.figure.Figure
        The figure with subplots.
    """
    if flag_degrees:
        val = 'valueVectorDeg'
        avg = 'meanValueVectorDeg'
    else:
        val = 'valueVector'
        avg = 'meanValueVector'

    n_lines = session['nBlocks'] // len(session['design']['blocks'])
    fig, axes = plt.subplots(n_lines, 4, figsize=(16, 3 * n_lines))
    if n_lines == 1:
        axes = axes.reshape(1, -1)

    for i_block in range(session['nBlocks']):
        row = i_block // 4
        col = i_block % 4
        ax = axes[row, col]

        stim = session['blocks'][i_block]['stim']
        ax.plot(stim['time'], stim[val], '-k', linewidth=0.5)
        ax.plot(stim['time'], stim[avg], '-y', linewidth=2)
        ax.set_title(f'block type {session["blocks"][i_block]["blockType"]}')

    plt.tight_layout()
    return fig
