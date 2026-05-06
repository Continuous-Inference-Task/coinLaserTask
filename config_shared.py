"""
config_shared.py — values shared between sequence generation and experiment runtime.

Imported by both ``stimgen/laser/config.py`` and ``laserTask/config.py``.
Keep this file dependency-free (no psychopy, no numpy) so both sides can
import it without pulling in each other's stack.
"""

# NOTE: these three constants are the *only* things that must stay
# in sync between the stimgen and the experiment runner.  Change them
# here and both sides pick up the update automatically.

SEQUENCE_VERSION: str = "v4"
"""Version tag for main / baseline / online-training laser sequences."""

PRACTICE_SEQUENCE_VERSION: str = "v3"
"""Version tag for practice laser sequences."""

SEQUENCE_ROOT: str = "sequences/"
"""Root directory for generated sequence CSV files (relative to project root)."""
