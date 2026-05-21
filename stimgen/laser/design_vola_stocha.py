"""
design_vola_stocha — Build the block design from active volatility and noise selections.

The block types are the Cartesian product of the selected volatility levels
and noise levels from config.py.  One session = one full set (fully balanced).

Can also be called with explicit lists to generate a design for a specific
session type (practice vs main).
"""
import config


def design_vola_stocha(volatility=None, noise=None, noise_mode=None):
    """Return a design dict with block types generated from the given dimensions.

    Parameters
    ----------
    volatility : list of str or None
        Volatility preset names (keys into config.VOLATILITY_PRESETS).
        If None, uses config.MAIN_VOLATILITY.
    noise : list of str or None
        Noise preset names (keys into config.NOISE_PRESETS).
        If None, uses config.MAIN_NOISE.
    noise_mode : str or None
        How noise is combined with volatility. "counterbalanced" (all cross product)
        or "stable_only" (only stable gets all noise levels, others get only the first).

    Returns
    -------
    dict with keys 'blockTypes' (list of str) and 'blocks' (list of dicts).
    Each block dict has 'durMeanStdMinMax', 'noiseStd', and 'jumpValueSet'.
    """
    if volatility is None:
        volatility = config.MAIN_VOLATILITY
    if noise is None:
        noise = config.MAIN_NOISE
    if noise_mode is None:
        # Determine based on whether volatility matches practice
        if volatility == config.PRACTICE_VOLATILITY:
            noise_mode = getattr(config, "PRACTICE_NOISE_MODE", "counterbalanced")
        else:
            noise_mode = getattr(config, "MAIN_NOISE_MODE", "counterbalanced")

    block_types = []
    blocks = []

    for v_label in volatility:
        v_params = config.VOLATILITY_PRESETS[v_label]
        
        # If noise_mode is '<vola>_only' and this is not that vola block, only use the first noise level
        active_noise = noise
        if noise_mode and noise_mode.endswith("_only"):
            vola_only = noise_mode[:-5]
            if v_label != vola_only and len(noise) > 0:
                active_noise = [noise[0]]
            
        for n_label in active_noise:
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


def get_block_count(volatility=None, noise=None, noise_mode=None):
    """Return the total number of block types for the given dimensions."""
    design = design_vola_stocha(volatility, noise, noise_mode)
    return len(design['blockTypes'])
