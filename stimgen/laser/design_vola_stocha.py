"""
designVolaStocha - A task design with a manipulation of mean
jump probability ("volatility").
"""
import config


def design_vola_stocha():
    """Returns a design dict with block types and block parameters."""
    design = {}
    design['blockTypes'] = ['stablePrecise', 'stableNoisy', 'volatilePrecise', 'volatileNoisy']

    blocks = [None] * 4

    # Block type 1: slow changes, precise
    blocks[0] = {
        'durMeanStdMinMax': config.DUR_MEAN_STD_MIN_MAX_STABLE,
        'noiseStd': config.NOISE_STD_LOW,
    }

    # Block type 2: slow changes, noisy
    blocks[1] = {
        'durMeanStdMinMax': config.DUR_MEAN_STD_MIN_MAX_STABLE,
        'noiseStd': config.NOISE_STD_HIGH,
    }

    # Block type 3: fast changes, precise
    blocks[2] = {
        'durMeanStdMinMax': config.DUR_MEAN_STD_MIN_MAX_VOLATILE,
        'noiseStd': config.NOISE_STD_LOW,
    }

    # Block type 4: fast changes, noisy
    blocks[3] = {
        'durMeanStdMinMax': config.DUR_MEAN_STD_MIN_MAX_VOLATILE,
        'noiseStd': config.NOISE_STD_HIGH,
    }

    # What stays constant over blocks
    for block in blocks:
        # Jump sizes in deg
        block['jumpValueSet'] = config.JUMP_VALUE_SET

    design['blocks'] = blocks
    return design
