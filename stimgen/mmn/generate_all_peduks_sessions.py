"""Convenience entry point — generates the standard PEDUKS sessions.

Equivalent to ``generateAllPeduksSessions.m``.
"""

from __future__ import annotations

from typing import Any, Dict

from .generate_tone_session import generate_tone_session


def generate_all_peduks_sessions(output_dir: str = ".") -> Dict[str, Any]:
    """Generate the standard 12-block MMN session.

    The block sequence is::

        [1, 2, 3, 3,  1, 2, 3, 3,  1, 2, 3, 3]

    where ``1`` = stableNoisy, ``2`` = volatileNoisy,
    ``3`` = volatilePrecise.

    Writes ``mmn_session.mat`` and ``mmn_block1.csv`` through
    ``mmn_block12.csv`` to *output_dir*.

    Parameters
    ----------
    output_dir : str
        Directory to write output files to.  To write directly into
        the project's sequences directory, use
        ``generate_all_peduks_sessions("../../sequences/mmn")``.

    Returns
    -------
    dict
        Full session structure (see :func:`generate_tone_session`).
    """
    block_sequence = [1, 2, 3, 3, 1, 2, 3, 3, 1, 2, 3, 3]
    return generate_tone_session("mmn", block_sequence, output_dir)