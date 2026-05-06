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

    # Block type 1: slow changes, precise
    blocks[0] = {
        'sigmaStream': 1.5,
        'sigmaObs': config.NOISE_STD_LOW,
    }

    # Block type 2: slow changes, noisy
    blocks[1] = {
        'sigmaStream': 1.5,
        'sigmaObs': config.NOISE_STD_HIGH,
    }

    # Block type 3: fast changes, precise
    blocks[2] = {
        'sigmaStream': 3,
        'sigmaObs': config.NOISE_STD_LOW,
    }

    # Block type 4: fast changes, noisy
    blocks[3] = {
        'sigmaStream': 3,
        'sigmaObs': config.NOISE_STD_HIGH,
    }

    design['blocks'] = blocks
    return design
