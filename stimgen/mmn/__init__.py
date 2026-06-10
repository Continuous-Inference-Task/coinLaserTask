"""PEDUKS MMN stimulus generator — Python port.

Generates tone sequences for auditory Mismatch Negativity (MMN) paradigms
with stable and volatile environments.  Algorithmically identical to the
original MATLAB code in ``peduks_mmn_stimgen/``.

MMN blocks are now generated inline as part of the laser sequence
generation workflow — one MMN block per laser block, with the same
block duration and volatility/noise coupling.

Exports
-------
mmn_design
generate_block_sequence
compute_sequence_stats
generate_tone_session
generate_mmn_blocks
"""

from .mmn_design import mmn_design
from .generate_block_sequence import generate_block_sequence
from .compute_sequence_stats import compute_sequence_stats
from .generate_tone_session import generate_tone_session, write_block_csv_files
from .generate_mmn_blocks import generate_mmn_blocks

__all__ = [
    "mmn_design",
    "generate_block_sequence",
    "compute_sequence_stats",
    "generate_tone_session",
    "write_block_csv_files",
    "generate_mmn_blocks",
]
