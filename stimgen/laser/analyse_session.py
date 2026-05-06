"""
analyseSession - Analyses and plots session statistics (mean movement and
step sizes per condition).
"""
import numpy as np
import matplotlib.pyplot as plt
from laser_colours import laser_colours


def analyse_session(session):
    """
    Analyse a session by plotting mean movement and step size distributions.

    Parameters
    ----------
    session : dict
        Session dict with 'nBlocks', 'blocks', 'blockTypes', 'design'.

    Returns
    -------
    fig1 : matplotlib.figure.Figure
        Figure showing overall movement per condition/session.
    fig2 : matplotlib.figure.Figure
        Figure showing step size distributions.
    """
    col = laser_colours()
    cond_colors = [col['stablePrecise'], col['stableNoisy'],
                   col['volatilePrecise'], col['volatileNoisy']]
    cond_labels = session['blockTypes']

    n_ses = session['nBlocks'] // 4

    # Figure 1: Sum of overall mean movement
    fig1, ax1 = plt.subplots()
    offset = [-0.1, -0.05, 0.05, 0.1]
    ph = [None] * 4
    for i_ses in range(n_ses):
        for i_block in range(4):
            i_block_total = i_ses * 4 + i_block
            condition = session['blocks'][i_block_total]['blockID']
            mean_vals = session['blocks'][i_block_total]['stim']['meanValues']
            move = np.sum(np.abs(np.diff(mean_vals)))

            ph[i_block] = ax1.plot(
                i_ses + 1 + offset[i_block], move, 'o',
                color=cond_colors[condition - 1],
                markerfacecolor=cond_colors[condition - 1]
            )[0]

    ax1.legend(ph, cond_labels, loc='right', frameon=False)
    ax1.set_xticks(range(1, n_ses + 1))
    ax1.set_xlim(0.5, n_ses + 0.5)
    ax1.set_xlabel('session')
    ax1.set_ylabel('sum(mean steps)')
    ax1.set_title('overall movement per condition, session')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # Figure 2: Number of steps of different sizes
    fig2, axes2 = plt.subplots(1, n_ses, figsize=(4 * n_ses, 4))
    if n_ses == 1:
        axes2 = [axes2]
    n_steps = np.zeros((n_ses, 4, 3))
    for i_ses in range(n_ses):
        ax = axes2[i_ses]
        ph2 = [None] * 4
        for i_block in range(4):
            i_block_total = i_ses * 4 + i_block
            mean_vals = session['blocks'][i_block_total]['stim']['meanValues']
            steps = np.abs(np.diff(mean_vals))
            n_steps[i_ses, i_block, 0] = np.sum(steps == 20)
            n_steps[i_ses, i_block, 1] = np.sum(steps == 30)
            n_steps[i_ses, i_block, 2] = np.sum(steps == 40)

            ph2[i_block] = ax.plot(
                [1, 2, 3], n_steps[i_ses, i_block, :], '-o',
                color=cond_colors[i_block],
                markerfacecolor=cond_colors[i_block]
            )[0]

        ax.set_title(f'session {i_ses + 1}')
        if i_ses == 0:
            ax.set_ylabel('number of steps')
            ax.legend(ph2, cond_labels, frameon=False)
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels(['small', 'medium', 'large'])
        ax.set_xlabel('step size')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    # Link y-axes
    y_min = min(ax.get_ylim()[0] for ax in axes2)
    y_max = max(ax.get_ylim()[1] for ax in axes2) + 4
    for ax in axes2:
        ax.set_ylim(y_min, y_max)

    print('nJumps per condition:')
    print(np.sum(n_steps, axis=(0, 2)))

    return fig1, fig2
