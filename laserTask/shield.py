from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class EventReward:
    # Signed currency delta for one event (e.g., hit or miss).
    total: float = 0.0
    # Optional per-event override; falls back to ShieldSizeConfig.bar_scale.
    bar_scale: Optional[float] = None
    # Optional per-event reward-bar colour override.
    colour: Optional[List[float]] = None


@dataclass
class FramingProfile:
    hit: EventReward = field(default_factory=EventReward)
    miss: EventReward = field(default_factory=EventReward)


@dataclass
class ShieldSize:
    # Angular half-width of this shield in degrees.
    degrees: float
    # Reward profile used in loss framing (wins=0).
    loss: FramingProfile = field(default_factory=FramingProfile)
    # Reward profile used in win framing (wins=1).
    win: FramingProfile = field(default_factory=FramingProfile)


@dataclass
class ShieldSizeConfig:
    # Ordered shield options (smallest -> largest).
    sizes: List[ShieldSize]
    # Start index applied at block start.
    default_index: int = 0
    # Global money->bar conversion unless an event overrides it.
    bar_scale: float = 2.5
    key_shrink: str = "s"
    key_grow: str = "w"

    def __post_init__(self) -> None:
        if not self.sizes:
            raise ValueError("sizes must contain at least one ShieldSize")
        if not 0 <= self.default_index < len(self.sizes):
            raise ValueError(
                f"default_index {self.default_index} out of range for "
                f"{len(self.sizes)} sizes"
            )

    def get_reward(
        self, size_index: int, wins: int, is_hit: bool
    ) -> Tuple[float, float, Optional[List[float]]]:
        # Central lookup so downstream code stays config-driven.
        size = self.sizes[size_index]
        profile = size.win if wins else size.loss
        event = profile.hit if is_hit else profile.miss
        scale = event.bar_scale if event.bar_scale is not None else self.bar_scale
        return event.total, scale, event.colour

    @property
    def min_index(self) -> int:
        return 0

    @property
    def max_index(self) -> int:
        return len(self.sizes) - 1

    @property
    def size_degrees(self) -> List[float]:
        return [size.degrees for size in self.sizes]

    @property
    def default_degrees(self) -> float:
        return self.size_degrees[self.default_index]

    @classmethod
    def fixed_custom(cls, degrees: float = 20.0, loss_factor: float = 0.003) -> "ShieldSizeConfig":
        lf = loss_factor
        return cls(
            sizes=[
                ShieldSize(
                    degrees=degrees,
                    loss=FramingProfile(
                        hit=EventReward(total=0.0, colour=[-1, 1, -1]),
                        miss=EventReward(total=-lf, colour=[1, -1, -1]),
                    ),
                    win=FramingProfile(
                        hit=EventReward(
                            total=+lf,
                            colour=[-1, 1, -1],
                        ),
                        miss=EventReward(total=0.0, colour=[1, -1, -1]),
                    ),
                )
            ],
            default_index=0,
        )

    @classmethod
    def peduks_fixed(cls, loss_factor: float = 0.003) -> "ShieldSizeConfig":
        lf = loss_factor
        return cls(
            sizes=[
                ShieldSize(
                    degrees=20.0,
                    loss=FramingProfile(
                        hit=EventReward(total=0.0, colour=[-1, 1, -1]),
                        miss=EventReward(total=-lf, colour=[1, -1, -1]),
                    ),
                    win=FramingProfile(
                        hit=EventReward(
                            total=+lf,
                            colour=[-1, 1, -1],
                        ),
                        miss=EventReward(total=0.0, colour=[1, -1, -1]),
                    ),
                )
            ],
            default_index=0,
        )

    @classmethod
    def adjustable_standard(cls, loss_factor: float = 0.003) -> "ShieldSizeConfig":
        lf = loss_factor
        return cls(
            sizes=[
                ShieldSize(
                    degrees=10.0,
                    loss=FramingProfile(
                        hit=EventReward(total=0.0, colour=[-1, 1, -1]),
                        miss=EventReward(total=-lf, colour=[1, -1, -1]),
                    ),
                    win=FramingProfile(
                        hit=EventReward(total=lf, colour=[-1, 1, -1]),
                        miss=EventReward(total=0.0, colour=[1, -1, -1]),
                    ),
                ),
                ShieldSize(
                    degrees=20.0,
                    loss=FramingProfile(
                        hit=EventReward(total=-(lf / 3.0), colour=[-1, 1, -1]),
                        miss=EventReward(total=-lf, colour=[1, -1, -1]),
                    ),
                    win=FramingProfile(
                        hit=EventReward(total=lf * (2.0 / 3.0), colour=[-1, 1, -1]),
                        miss=EventReward(total=0.0, colour=[1, -1, -1]),
                    ),
                ),
                ShieldSize(
                    degrees=30.0,
                    loss=FramingProfile(
                        hit=EventReward(total=-(lf / 2.0), colour=[-1, 1, -1]),
                        miss=EventReward(total=-lf, colour=[1, -1, -1]),
                    ),
                    win=FramingProfile(
                        hit=EventReward(total=lf / 2.0, colour=[-1, 1, -1]),
                        miss=EventReward(total=0.0, colour=[1, -1, -1]),
                    ),
                ),
            ],
            default_index=1,
        )
