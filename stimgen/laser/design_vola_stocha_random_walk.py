"""
designVolaStochaRandomWalk - A task design with a manipulation of mean
jump probability ("volatility") for the random walk version.
"""
import config


def design_vola_stocha_random_walk():
    """Returns a design dict with block types and block parameters for random walk."""
    design = {}
    design['blockTypes'] = ['stablePrecise', 'stableNoisy', 'volatilePrecise', 'volatileNoisy']

    blocks = [None] * 4

    precise_val = config.NOISE_PRESETS.get("precise", 10)
    noisy_val = config.NOISE_PRESETS.get("noisy", 20)

    # Block type 1: slow changes, precise
    blocks[0] = {
        'sigmaStream': 1.5,
        'sigmaObs': precise_val,
    }

    # Block type 2: slow changes, noisy
    blocks[1] = {
        'sigmaStream': 1.5,
        'sigmaObs': noisy_val,
    }

    # Block type 3: fast changes, precise
    blocks[2] = {
        'sigmaStream': 3,
        'sigmaObs': precise_val,
    }

    # Block type 4: fast changes, noisy
    blocks[3] = {
        'sigmaStream': 3,
        'sigmaObs': noisy_val,
    }

    design['blocks'] = blocks
    return design
