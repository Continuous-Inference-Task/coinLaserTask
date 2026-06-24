from abc import ABC, abstractmethod
from typing import List, Optional

from laserTask.config import ExperimentConfig


class BaseRewardTracker(ABC):
    """Interface that all reward functions must implement.
    
    To add a new reward function, subclass this and implement
    all abstract methods. Pass your subclass to run_experiment() in main.py."""

    @abstractmethod
    def reset_block(self) -> None:
        """Initialise reward state for a new block"""
        pass

    @abstractmethod
    def update(self, is_hit: bool, is_new_evidence: bool) -> None:
        """Update reward state based on current hit status for one frame."""
        pass

    @abstractmethod
    def end_block(self) -> None:
        """Finalise block and accumulate session total."""
        pass

    @property
    @abstractmethod
    def session_total_text(self) -> str:
        """Formatted session total for display."""
        pass


class RewardTracker(BaseRewardTracker):
    """Track reward state across frames and blocks.

    Handles both *loss framing* (``wins=0``: start high, lose on miss)
    and *win framing* (``wins=1``: start low, gain on hit).

    Parameters
    ----------
    config : ExperimentConfig
    wins   : int   0 = loss framing, 1 = win framing
    """

    BAR_BOTTOM = -0.3   # y-coordinate of the bar's bottom edge

    def __init__(self, config: ExperimentConfig, wins: int = 0):
        self.cfg = config
        self.wins = wins
        self.shield_size = config.shield_sizes
        self.session_total: float = 0.0
        self.reset_block()

    @property
    def bar_position(self) -> float:
        """Centre y-coordinate of the reward bar (derived from bar_length)."""
        return self.BAR_BOTTOM + self._bar_length / 2

    @property
    def bar_length(self) -> float:
        return self._bar_length

    @bar_length.setter
    def bar_length(self, value: float) -> None:
        self._bar_length = max(value, 0.0)  # floor at zero

    def reset_block(self):
        """Initialise reward variables for a new block."""
        if self.wins == 0:
            self.bar_length = 0.5
            self.total = 2.0
            self.top_amount = 1.0
            self.bottom_amount = 0.8
            self.change_color = [1, -1, -1]    # red for losses
        else:
            self._bar_length = 0.001
            self.total       = 0.0 
            self.top_amount  = 0.2    
            self.bottom_amount = 0.0 
            self.change_color  = [-1, 1, -1]   # green for gains
        self.flash_bar_length = 0.0

    def update(
        self, 
        is_hit: bool, 
        is_new_evidence: bool, 
        size_index: Optional[int] = None,
    ) -> None:
        """Call once per frame with the current hit status.

        Only modifies reward on frames where new evidence (a laser
        position change) is presented.
        """
        if not is_new_evidence:
            return
        # Keep callers backward-compatible: if no size is provided, use config default.
        if size_index is None:
            size_index = self.shield_size.default_index
        if is_hit:
            self._on_hit(size_index)
        else:
            self._on_miss(size_index)
        self._clamp()

    # -- internal --------------------------------------------------------- #
    def _on_hit(self, size_index: int) -> None:
        # Lookup delegates all framing/size-specific logic to ShieldSizeConfig.
        total, scale, magnitude, colour = self.shield_size.get_reward(
            size_index, self.wins, True
        )
        self._apply_event(total, scale, magnitude, colour)

    def _on_miss(self, size_index: int) -> None:
        # Misses use the same config-driven lookup path as hits.
        total, scale, magnitude, colour = self.shield_size.get_reward(
            size_index, self.wins, False
        )
        self._apply_event(total, scale, magnitude, colour)


    # TODO: if flash_feedback = True: make size of flash equivalent to lf, somehow, irrespective of whether total goes up or down
    # TODO: figure out how to access lf from here
    def _apply_event(
        self, total: float, scale: float, magnitude: float, colour: Optional[List[float]]
    ) -> None:
        # Negative totals are losses, positive totals are gains, zero is neutral.
        self.flash_bar_length = magnitude * scale 

        self.total += total

        if total != 0:
            self._bar_length += scale * total

        # Only override colour when the event explicitly asks for it.
        if colour is not None:
            self.change_color = colour

    def _set_floor(self):
        self.bar_length = 1e-5
        self.total = 0.0
        self.flash_bar_length = 0.0

    def _clamp(self):
        """Handle bar-wrap and floor for both framing conditions."""
        if self.wins == 0 and self.bar_length <= 0:
            self.bar_length = 0.5
            self.top_amount -= 0.2
            self.bottom_amount -= 0.2
        if self.wins == 1:
            if self.bar_length >= 0.5:
                self.bar_length = 0.001
                self.top_amount += 0.2
                self.bottom_amount += 0.2
            elif self.bar_length <= 0:
                self.bar_length = 0.5
                self.top_amount -= 0.2
                self.bottom_amount -= 0.2
        if self.total < 0: # changed from <= 0
            self.total = 0.0
            if self.wins == 0:
                self.bar_length = 0.25
                self.top_amount = 0.2
                self.bottom_amount = 0.0
            else:
                self.bar_length = 1e-5
                self.flash_bar_length = 0
                self.top_amount = 0.2 # NOTE: changed from 1
                self.bottom_amount = 0

    def end_block(self):
        """Add block reward to session running total."""
        self.session_total += self.total

    # -- formatted text --------------------------------------------------- #
    @property
    def top_text(self) -> str:
        return f"{self.cfg.currency_symbol}{self.top_amount:.2f}"

    @property
    def bottom_text(self) -> str:
        return f"{self.cfg.currency_symbol}{self.bottom_amount:.2f}"

    @property
    def reward_text(self) -> str:
        return f"{self.cfg.currency_symbol}{self.total:.2f}"

    @property
    def session_total_text(self) -> str:
        return f"{self.cfg.currency_symbol}{self.session_total:.2f}"
