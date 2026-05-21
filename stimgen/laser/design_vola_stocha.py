"""
design_vola_stocha — Build the block design from active volatility and noise selections.

The block types are the Cartesian product of the selected volatility levels
and noise levels from config.py.  One session = one full set (fully balanced).

Can also be called with explicit lists to generate a design for a specific
session type (practice vs main).
"""
import config


def design_vola_stocha(volatility=None, noise=None):
    """Return a design dict with block types generated from the given dimensions.

    Parameters
    ----------
    volatility : list of str or None
        Volatility preset names (keys into config.VOLATILITY_PRESETS).
        If None, uses config.MAIN_VOLATILITY.
    noise : list of str or None
        Noise preset names (keys into config.NOISE_PRESETS).
        If None, uses config.MAIN_NOISE.

    Returns
    -------
    dict with keys 'blockTypes' (list of str) and 'blocks' (list of dicts).
    Each block dict has 'durMeanStdMinMax', 'noiseStd', and 'jumpValueSet'.
    """
    if volatility is None:
        volatility = config.MAIN_VOLATILITY
    if noise is None:
        noise = config.MAIN_NOISE

    block_types = []
    blocks = []

    for v_label in volatility:
        v_params = config.VOLATILITY_PRESETS[v_label]
        for n_label in noise:
            n_val = config.NOISE_PRESETS[n_label]
            block_types.append(f"{v_label}+{n_label}")
            blocks.append({
                'durMeanStdMinMax': v_params,
                'noiseStd': n_val,
                'jumpValueSet': config.JUMP_VALUE_SET,
            })

    return {
        'blockTypes': block_types,
        'blocks': blocks,
    }


def get_block_count(volatility=None, noise=None):
    """Return the total number of block types for the given dimensions."""
    if volatility is None:
        volatility = config.MAIN_VOLATILITY
    if noise is None:
        noise = config.MAIN_NOISE
    return len(volatility) * len(noise)
