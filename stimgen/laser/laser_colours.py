"""
laser_colours - Colour definitions for each condition in the laser task.
"""
import numpy as np


def laser_colours():
    """Returns a dict of RGB colour arrays for each condition."""
    col = {
        'stablePrecise': np.array([67, 147, 195]) / 255,
        'stableNoisy': np.array([146, 197, 222]) / 255,
        'volatilePrecise': np.array([214, 96, 77]) / 255,
        'volatileNoisy': np.array([244, 165, 130]) / 255,
    }
    return col
