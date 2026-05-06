"""PEDUKS MMN stimulus generator — Python port.

Generates tone sequences for auditory Mismatch Negativity (MMN) paradigms
with stable and volatile environments.  Algorithmically identical to the
original MATLAB code in ``peduks_mmn_stimgen/``.

Quick start::

    >>> from stimgen.mmn import generate_all_peduks_sessions
    >>> session = generate_all_peduks_sessions()

Exports
-------
mmn_design
generate_block_sequence
compute_sequence_stats
generate_tone_session
write_block_csv_files
generate_all_peduks_sessions
"""

from .mmn_design import mmn_design
from .generate_block_sequence import generate_block_sequence
from .compute_sequence_stats import compute_sequence_stats
from .generate_tone_session import generate_tone_session, write_block_csv_files
from .generate_all_peduks_sessions import generate_all_peduks_sessions

__all__ = [
    "mmn_design",
    "generate_block_sequence",
    "compute_sequence_stats",
    "generate_tone_session",
    "write_block_csv_files",
    "generate_all_peduks_sessions",
]
