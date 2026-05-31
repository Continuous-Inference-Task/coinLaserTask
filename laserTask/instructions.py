from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

from laserTask.config import ExperimentConfig

# TODO: in long run want to make instruction screen easily adaptable
def build_shield_instructions(cfg: ExperimentConfig, winds_cond: int) -> str:
    """Return the participant-facing text explaining shield-size controls
    and their reward consequences.

    The text adapts automatically to the number of sizes, their values,
    the assigned keys, and the reward framing (loss vs. win).
    """
    sds = cfg.shield_sizes
    n = len(sds.sizes)

    def _fmt_money(amount: float) -> str:
        value = f"{abs(amount):.5f}".rstrip("0").rstrip(".")
        if "." not in value:
            value = f"{value}.00"
        return f"{cfg.currency_symbol}{value}"

    def _event_text(amount: float) -> str:
        if amount > 0:
            return f"you gain {_fmt_money(amount)} when you catch a beam"
        if amount < 0:
            return f"you lose {_fmt_money(amount)} when you catch a beam"
        return "no change when you catch a beam"

    def _miss_text(amount: float) -> str:
        if amount > 0:
            return f"When you miss a beam, you gain {_fmt_money(amount)}."
        if amount < 0:
            return f"When you miss a beam, you lose {_fmt_money(amount)}."
        return "When you miss a beam, there is no score change."

    # readable labels
    labels: List[str] = []
    for i, sz in enumerate(sds.sizes):
        tag = ""
        if i == 0:
            tag = " (smallest)"
        elif i == n - 1:
            tag = " (largest)"
        labels.append(f"{sz.degrees:.0f}°{tag}")


    if winds_cond == 0:
        # --- loss framing ---
        lines = []
        for lbl, size in zip(labels, sds.sizes):
            lines.append(f"  • {lbl}:  {_event_text(size.loss.hit.total)}")
        consequence = "\n".join(lines)
        miss_values = [size.loss.miss.total for size in sds.sizes]
        hint = "A smaller shield is harder to aim but protects your score better!"
    else:
        # --- win framing ---
        lines = []
        for lbl, size in zip(labels, sds.sizes):
            lines.append(f"  • {lbl}:  {_event_text(size.win.hit.total)}")
        consequence = "\n".join(lines)
        miss_values = [size.win.miss.total for size in sds.sizes]
        hint = "A smaller shield is harder to aim but earns you more when you succeed!"

    if len(set(miss_values)) == 1:
        # Keep text compact when miss outcome is identical for all sizes.
        miss_line = f"{_miss_text(miss_values[0])} This is the same for all shield sizes."
    else:
        # Otherwise show explicit per-size miss consequences.
        miss_line = "Miss outcome by shield size:\n" + "\n".join(
            f"  • {lbl}: {_miss_text(total).replace('When you miss a beam, ', '')}"
            for lbl, total in zip(labels, miss_values)
        )

    default_sz = sds.default_degrees

    _keyboard_shield_blurb = (
        f"Press  '{sds.key_shrink.upper()}'  to make the shield SMALLER.\n"
        f"Press  '{sds.key_grow.upper()}'  to make the shield LARGER.\n\n"
    )
    _box_shield_blurb = (
        "Use the second response box to make the shield smaller or larger.\n\n"
    )
    _shield_blurb = (
        _keyboard_shield_blurb
        if cfg.input_device == "keyboard"
        else _box_shield_blurb
    )

    return (
        "Shield Size\n\n"
        # f"Press  '{sds.key_shrink.upper()}'  to make the shield SMALLER.\n"
        # f"Press  '{sds.key_grow.upper()}'  to make the shield LARGER.\n\n"
        f"{_shield_blurb}"
        f"There are {n} sizes.  Each block starts at the default "
        f"size ({default_sz:.0f}°).\n\n"
        f"{hint}\n\n"
        f"Reward by shield size:\n"
        f"{consequence}\n\n"
        f"{miss_line}\n\n"
        "Press any key to continue."
    )

# def build_basic_shield_instructions(cfg: ExperimentConfig, winds_cond: int) -> str:
#     _keyboard_shield_blurb = (
#         f"Press  '{cfg.key_left.upper()}'  to make the shield SMALLER.\n"
#         f"Press  '{cfg.key_right.upper()}'  to make the shield LARGER.\n\n"
#     )
#     _box_shield_blurb = (
#         "Use the second response box to make the shield smaller or larger.\n\n"
#     )
#     _shield_blurb = (
#         _keyboard_shield_blurb
#         if cfg.input_device == "keyboard"
#         else _box_shield_blurb
#     )

# ── Tag enum – identity only, no logic ───────────────────────────────────── #
class InstructionSet(str, Enum):
    COGPSY = "cogpsy"
    PEDUKS = "peduks"


# ── One screen = one wait_for_key() call ──────────────────────────────────── #
@dataclass
class ScreenSpec:
    """Declarative description of one instruction screen.

    stim_keys : keys to pull from S{}; can be TextStims *or* ImageStims.
    log_label : forwarded to wait_for_key(label=...) and logging.exp().
    shown_if  : optional predicate; screen is silently skipped when False.
    """
    stim_keys: List[str]
    log_label: str
    shown_if: Optional[Callable[[ExperimentConfig], bool]] = None

    def visible(self, cfg: ExperimentConfig) -> bool:
        return self.shown_if is None or self.shown_if(cfg)


# ── Abstract strategy ─────────────────────────────────────────────────────── #

class InstructionProfile(ABC):
    """Owns all participant-facing text for one experiment variant
    and declares at which phase each screen appears."""

    @abstractmethod
    def stim_texts(self, cfg: ExperimentConfig, winds_cond: int) -> Dict[str, str]:
        """Return {stim_key: text} for every instruction TextStim.
        create_stimuli() builds one TextStim per entry with uniform style."""
        ...

    @abstractmethod
    def pre_experiment(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        """Shown once before anything else."""
        ...

    @abstractmethod
    def pre_practice(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        """Shown before the first practice block."""
        ...

    @abstractmethod
    def post_practice(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        """Shown after the last practice block."""
        ...

    @abstractmethod
    def pre_main(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        """Shown once at the transition into the main phase."""
        ...

    @abstractmethod
    def post_block(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        """Shown after each main block."""
        ...

    @abstractmethod
    def post_main(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        """Shown once after the last main block."""
        ...


# ── Concrete profiles ─────────────────────────────────────────────────────── #

class CogPsyProfile(InstructionProfile):

    def stim_texts(
        self, 
        cfg: ExperimentConfig, 
        winds_cond: int,
        n_main_blocks: Optional[int] = None,
        block_duration_min: float = 3.0,
        practice_block_duration_min: float = 1.0,
    ) -> Dict[str, str]:
        _kb = cfg.input_device == "keyboard"
        _move = (
            f"Press {cfg.key_right.upper()} / {cfg.key_left.upper()} to move the shield."
            if _kb
            # TODO: make this more useable for response box users
            else f"To navigate the shield, use the \"1\" and \"2\" buttons on your response box. "
        )
        _start = (
            "You will also hear tones through your headphones. "
            "These are unrelated to the game – you can ignore them.\n\n"
            "Press any key to start."
            if cfg.enable_audio
            else "Press any key to start."
        )
        _advance = (
            f"press {cfg.key_next.upper()} to advance to the next screen."
            if _kb
            else "press button \"3\" to advance to the next screen."
        )

        _dur_val = int(block_duration_min) if block_duration_min.is_integer() else round(block_duration_min, 1)
        _dur_str = f"{_dur_val} min"

        # Dynamic practice instructions
        _practice_keys = (
            f"'{cfg.key_left.upper()}' and '{cfg.key_right.upper()}' keys"
            if cfg.input_device == "keyboard"
            else "left and right buttons of the response box"
        )
        _prac_dur_val = int(practice_block_duration_min) if practice_block_duration_min.is_integer() else round(practice_block_duration_min, 1)
        _prac_dur_str = f"{_prac_dur_val} min"

        return {
            "title": (
                "Save-the-world task"
            ),
            "instr1": (
                "Welcome to the Save-the-world game!\n\n"
                "Mysterious radioactive sources have just landed on Earth …\n\n"
                f"Press any key to continue."
            ),
            "shield_instr1": (
                "Your shield can be positioned on a circle around the harmful radiation source.\n"
                f"{_move} Try it now!\n\n"
                f"If you have understood how to move the shield, \n{_advance}"
            ),
            "shield_instr2": (
                build_shield_instructions(cfg, winds_cond),
            ),
            "reward_instr": (
                "In every block of this game, your reward for saving the world "
                "from this radiation starts off at £1. The more radiation you let "
                "through, the more reward you lose.\n\n"
                "Try to keep as much of that £1 as you can by catching as many "
                "beams as you can. After every block, you will receive feedback "
                "about how much reward you have earned in the previous block.\n\n"
                f"Each block will last {_dur_str}. A green circle will grow around "
                "the radioactive source, indicating how much time has passed. "
                "When the green circle is complete, the block is over.\n\n"
                "Press any key to continue."
            ),
            "practice_start_txt": (
                "You will now do a short practice block of the task. "
                f"This block will last {_prac_dur_str}.\n\n"
                "As in the real game, the source will emit radiation, but the main angle "
                "of attack might change over time, so that you have to keep monitoring "
                "the beams and decide when to re-position your shield.\n\n"
                "You will see a reward bar on the right of the screen, which shows you how "
                "you lose money whenever a beam remains uncaught, but you will not actually "
                f"earn any money during this practice. Remember to use the {_practice_keys} "
                "to navigate your shield.\n\n"
                "Press any key to start the practice block."
            ),
            "practice_end_txt": (
                "Well done - this was the practice block!\n\n"
                "As you have seen, the direction of the beams can jump around quickly, "
                "and you cannot catch all beams with your shield. That's ok - just try to "
                "catch as many as possible. The source will have a main direction of attack "
                "at any point - if you place your shield in that direction, you will catch most beams.\n\n"
                "Moving your shield also costs energy, which will be subtracted from your reward. "
                "It is thus important that you only move your shield when you think that the main "
                "direction of attack has changed.\n\n"
                "Press any key to continue."
            ),
            "main_start": _start,
            "main_task_instr": (
                "Are you ready to start the game?\n\n"
                "In the actual game:\n\n"
                "1. You will not see the reward bar - but the rules for earning "
                "money remain the same, and you will receive feedback about your "
                "reward after every block.\n\n"
                "2. Please focus your eyes on the centre of the radioactive "
                "source and do not follow the beams with your eyes. This is to "
                "minimise eye-movement artefacts in the MEG data.\n\n"
                "3. You will hear tones through your headphones while you play "
                "the game. These tones are completely unrelated to the task - "
                "you can ignore them and focus on catching the beams.\n\n"
                "Press any key to continue."
            ),
            "source_colours": (
                "You will encounter two different radioactive sources:\n"
                "A red and a blue source.\n\n\n\n\n\n\n\n"
                "The difference between these sources is how often they change "
                "their emission angle over time, and therefore how often you "
                "will have to adjust your shield position."
                "One of the sources will change its main angle of attack more "
                "often, whereas the other will remain stable for longer.\n\n"
                f"This game has {n_main_blocks if n_main_blocks is not None else cfg.n_blocks} blocks. "
                "You will encounter each source twice.\n\n"
                "Press any key to continue."
            ),
            "focus_instr": (
                "Please try to keep you eyes as fixed as possible on the centre of the screen.\n\n"
                "New source ahead:\n\n\n\n\n\n\n\n"
                "Press any key if you're ready to start.",
            ),
            "blk_end_pause": (
                "Well done. In this block, you earned:\n\n\n\n\n\n\nTake a short break."
            ),
            "blk_end_reward": (
                ""
            ),
            "blk_end_continue": (
                "Press any key to continue."
            ),
            "exp_end": (
                "Well done. You completed this task.\n"
                "Your total reward for saving the world is:\n\n\n\n\n"
                "Take a break."
            ),
            "final_reward": (
                ""
            )
        }

    def pre_experiment(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        return [
            ScreenSpec(["title", "instr1"], "instr1"),
            ScreenSpec(
                ["shield_instr1"], "shield_instr1"),
            ScreenSpec(
                ["shield_instr2"], "shield_instr2",
                shown_if=lambda c: c.allow_shield_adjustment,
            ),
            ScreenSpec(["reward_instr"], "reward_instr"),
        ]

    def pre_practice(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        return [ScreenSpec(["practice_start_txt"], "practice_start")]

    def post_practice(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        return [ScreenSpec(["practice_end_txt"], "practice_end")]

    def pre_main(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        return [
            ScreenSpec(["main_start"], "main_start"),
            ScreenSpec(["main_task_instr"], "main_task_instr"),
            # mix of TextStim and existing ImageStims – that's fine
            ScreenSpec(
                ["source_colours", "radioactive_colour1", "radioactive_colour2"],
                "source_colours",
            ),
            ScreenSpec(["focus_instr"], "focus_instr"),
        ]
    def post_block(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        return [
            ScreenSpec(["blk_end_pause", "blk_end_reward", "blk_end_continue"], "blk_end")
        ]
    
    def post_main(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        return [
            ScreenSpec(["exp_end", "final_reward"], "exp_end")
        ]


class PeduksProfile(InstructionProfile):
    """Shorter variant used in the PEDUKS study."""

    def stim_texts(
        self, 
        cfg: ExperimentConfig, 
        winds_cond: int,
        n_main_blocks: Optional[int] = None,
        block_duration_min: float = 3.0,
        practice_block_duration_min: float = 1.0,
    ) -> Dict[str, str]:
        _keyboard_move_blurb = (
            f"Use the '{cfg.key_left.upper()}' key to move the shield left "
            f"and the '{cfg.key_right.upper()}' key to move it right."
        )
        _box_move_blurb = (
            "Use the left and right hand-held button keys to navigate the shield."
        )
        _move_blurb = (
            _keyboard_move_blurb if cfg.input_device == "keyboard" else _box_move_blurb
        )

        _dur_val = int(block_duration_min) if block_duration_min.is_integer() else round(block_duration_min, 1)
        _dur_str = f"{_dur_val} min"

        return {
            "title": (
                "Are you ready to save the world?"
            ),
            "instr1": (
                "You will now play 1 session of the save-the-world game, "
                "where you protect our planet Earth by shielding it from "
                "harmful radiation.\n\n"
                f"This session will have {n_main_blocks if n_main_blocks is not None else cfg.n_blocks} blocks. "
                f"Each block lasts {_dur_str}.\n\n"
                f"{_move_blurb}\n\n"
                "Pay attention to the different sources and "
                "catch as many beams as you can!\n\n"
                "Press any key to continue."
            ),
            # build_shield_instructions() still works here
            "shield_instr": build_shield_instructions(cfg, winds_cond),
        }

    def pre_experiment(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        return [
            ScreenSpec(["title", "peduks_welcome"], "instr1"),
            ScreenSpec(["peduks_shield"], "shield_instr",
                shown_if=lambda c: c.allow_shield_adjustment,
            ),
        ]

    def pre_practice(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        return []   # PEDUKS has no practice

    def post_practice(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        return []

    def pre_main(self, cfg: ExperimentConfig) -> List[ScreenSpec]:
        return []   # drops straight into the first block


# ── Factory – the only place that knows about InstructionSet ─────────────── #

def get_profile(cfg: ExperimentConfig) -> InstructionProfile:
    match cfg.instruction_set:
        case InstructionSet.COGPSY:  return CogPsyProfile()
        case InstructionSet.PEDUKS: return PeduksProfile()
        case _: raise ValueError(f"Unknown instruction set: {cfg.instruction_set!r}")