from typing import Any, Dict, List, Optional

import numpy as np
from psychopy import visual

from laserTask.config import ExperimentConfig

# NOTE: RadialStim is imported lazily inside create_stimuli() only when
# cfg.round_pbar is True, so psychopy-visionscience remains an optional
# runtime dependency for studies that don't use the circular progress bar.

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


def compute_shield_vertices(
    shield_degrees: float,
    circle_radius: float,
    n_points: int = 40,
) -> list:
    """Return a pie-slice polygon spanning ±*shield_degrees* around 12 o'clock.

    Parameters
    ----------
    shield_degrees : float
        Half-angular-width of the shield (degrees).
    circle_radius : float
        Radius of the game circle.
    n_points : int
        Arc resolution (higher → smoother curve).

    Returns
    -------
    list of [x, y]
        Vertices starting at the origin, suitable for
        ``visual.ShapeStim.setVertices()``.

    Notes
    -----
    The original Builder script computed ``sin``/``cos`` via Euler's
    formula (``(e^{iθ}).imag / .real``) for JavaScript/PsychoJS
    compatibility.  Here we use ``numpy`` directly.
    """
    rad = np.radians(shield_degrees)
    scale = circle_radius * 1.1
    angles = np.linspace(-rad, rad, n_points)
    xs = np.sin(angles) * scale
    ys = np.cos(angles) * scale
    return [[0.0, 0.0]] + [[float(x), float(y)] for x, y in zip(xs, ys)]

# NOTE: adapted instructions specifically for Rob, need to make this modular

# ------------------------------------------------------------------ #
#  Instruction text override helper                                   #
# ------------------------------------------------------------------ #

def _load_instruction_text(cfg: ExperimentConfig, name: str, default: str) -> str:
    """Return override text from instruction_override_dir if available.

    Parameters
    ----------
    cfg : ExperimentConfig
    name : str
        Screen name (e.g. ``"title"``, ``"instr1"``, ``"shield_instr"``).
    default : str
        Fallback text used when no override file exists.

    Returns
    -------
    str
        The instruction text to display.
    """
    if not cfg.instruction_override_dir:
        return default
    from pathlib import Path
    override_path = Path(__file__).resolve().parent.parent / cfg.instruction_override_dir / f"{name}.txt"
    if override_path.is_file():
        return override_path.read_text(encoding="utf-8").strip()
    return default


def _has_instruction_override(cfg: ExperimentConfig, name: str) -> bool:
    """Check whether an override file exists for *name*."""
    if not cfg.instruction_override_dir:
        return False
    from pathlib import Path
    override_path = Path(__file__).resolve().parent.parent / cfg.instruction_override_dir / f"{name}.txt"
    return override_path.is_file()

def create_stimuli(
    win: visual.Window,
    cfg: ExperimentConfig,
    wins_cond: int,
    n_main_blocks: Optional[int] = None,
    block_duration_min: float = 3.0,
    practice_block_duration_min: float = 1.0,
) -> Dict[str, Any]:
    """Instantiate every ``visual.*`` component used by the experiment.

    Appearance is governed entirely by ``cfg.style``.  To change how
    anything looks, edit ``StimulusStyle`` — not this function.
    The shield-size instructions are generated from cfg by a separate function -- see build_shield_instructions().

    Returns
    -------
    dict  str → PsychoPy stimulus
    """
    s = cfg.style  # shorthand
    S: Dict[str, Any] = {}

    # Compute default shield-size vertices here (set once at block start)
    default_deg = cfg.shield_sizes.default_degrees
    init_verts = compute_shield_vertices(default_deg, cfg.circle_radius)

    # --- instruction / info screens ------------------------------------ #
    S["title"] = visual.TextStim(
        win,
        name="title",
        text=_load_instruction_text(cfg, "title", "Are you ready to save the world?"),
        font=s.font,
        pos=(0, 0.35),
        height=s.title_size,
        color=s.text_color,
    )

    # Change instruction screen based on input device
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

    S["instr1"] = visual.TextStim(
        win,
        name="instr1",
        text=_load_instruction_text(
            cfg,
            "instr1",
            (
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
        ),
        font=s.font,
        pos=(0, -0.08),
        height=s.small_text_size,
        wrapWidth=1.5,
        color=s.text_color,
    )

    # Shield instruction: default uses build_shield_instructions() when
    # allow_shield_adjustment is True, otherwise empty text.  An override
    # file (shield_instr.txt) replaces the text and forces the screen to
    # show even when allow_shield_adjustment is False.
    _shield_instr_default = (
        build_shield_instructions(cfg, wins_cond)
        if cfg.allow_shield_adjustment
        else ""
    )
    S["shield_instr"] = visual.TextStim(
        win,
        name="shield_instr",
        text=_load_instruction_text(cfg, "shield_instr", _shield_instr_default),
        font=s.font,
        pos=(0, 0),
        height=s.small_text_size,
        wrapWidth=1.5,
        color=s.text_color,
    )

    # reward_instr is an optional screen — only created when an override
    # file (reward_instr.txt) exists in instruction_override_dir.
    if _has_instruction_override(cfg, "reward_instr"):
        S["reward_instr"] = visual.TextStim(
            win,
            name="reward_instr",
            text=_load_instruction_text(cfg, "reward_instr", ""),
            font=s.font,
            pos=(0, 0),
            height=s.small_text_size,
            wrapWidth=1.5,
            color=s.text_color,
        )

    _tone_blurb = (
        "While playing the game, you will also hear tones through "
        "your headphones. These tones are completely unrelated to "
        "the game. We are using them to examine how you passively "
        "process auditory events. You can ignore the tones and "
        "focus on playing the game.\n\n\n"
        "When you are ready, press any key to start."
    )
    _no_tone_blurb = "When you are ready, press any key to start."
    S["main_start"] = visual.TextStim(
        win,
        name="main_start",
        text=_tone_blurb if cfg.enable_audio else _no_tone_blurb,
        font=s.font,
        pos=(0, 0),
        height=s.text_size,
        wrapWidth=1.5,
        color=s.text_color,
    )
    # Dynamic practice instructions
    _practice_keys = (
        f"'{cfg.key_left.upper()}' and '{cfg.key_right.upper()}' keys"
        if cfg.input_device == "keyboard"
        else "left and right buttons of the response box"
    )
    _prac_dur_val = int(practice_block_duration_min) if practice_block_duration_min.is_integer() else round(practice_block_duration_min, 1)
    _prac_dur_str = f"{_prac_dur_val} min"

    S["practice_start_txt"] = visual.TextStim(
        win,
        name="practice_start_text",
        text=(
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
        font=s.font,
        pos=(0, 0),
        height=s.small_text_size,
        wrapWidth=1.5,
        color=s.text_color,
    )

    S["practice_end_txt"] = visual.TextStim(
        win,
        name="practice_end_text",
        text=(
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
        font=s.font,
        pos=(0, 0),
        height=s.small_text_size,
        wrapWidth=1.5,
        color=s.text_color,
    )

    # main_task_instr is an optional screen — only created when an override
    # file (main_task_instr.txt) exists in instruction_override_dir.
    if _has_instruction_override(cfg, "main_task_instr"):
        S["main_task_instr"] = visual.TextStim(
            win,
            name="main_task_instr",
            text=_load_instruction_text(cfg, "main_task_instr", ""),
            font=s.font,
            pos=(0, 0),
            height=s.small_text_size,
            wrapWidth=1.5,
            color=s.text_color,
        )

    S["radioactive_colour1"] = visual.ImageStim(
        win,
        name="radioactive_colour1",
        image=cfg.image_root + "radioactive3.png",
        pos=(-0.2, 0.11),
        size=(0.2, 0.2),
        color=[1, 1, 1],
        colorSpace="rgb",
        interpolate=True,
    )

    S["radioactive_colour2"] = visual.ImageStim(
        win,
        name="radioactive_colour2",
        image=cfg.image_root + "radioactive2.png",
        pos=(0.2, 0.11),
        size=(0.2, 0.2),
        color=[1, 1, 1],
        colorSpace="rgb",
        interpolate=True,
    )

    S["source_colours"] = visual.TextStim(
        win,
        name="source_colours",
        text=(
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
        font=s.font,
        pos=(0, 0),
        height=s.small_text_size,
        wrapWidth=1.5,
        color=s.text_color,
    )

    # --- block start / end --------------------------------------------- #
    S["earth_background"] = visual.ImageStim(
        win,
        name="earth_background",
        image=None,
        ori=0.0,
        pos=[0, 0],
        size=[0.75, 0.75],
        flipHoriz=False,
        flipVert=False,
        texRes=128.0,
        interpolate=True,
    )

    S["blk_source_img"] = visual.ImageStim(
        win,
        name="block_source_img",
        image=None,
        pos=s.center_pos,
        size=s.source_size,
    )

    S["blk_start_txt"] = visual.TextStim(
        win,
        name="block_start_text",
        text=(
            "Please try to keep your eyes as fixed as possible on the centre "
            "of the screen.\n\n"
            "New source ahead:\n\n\n\n\n\n\n\n"
            "Press any key if you're ready to start."
        ),
        font=s.font,
        pos=(0, 0),
        height=s.text_size,
        color=s.text_color,
    )
    S["blk_id"] = visual.TextStim(
        win,
        name="block_id",
        text="",
        font="Open Sans",
        pos=(0, 0.4),
        height=s.text_size,
        color=s.text_color,
    )
    S["blk_end_label"] = visual.TextStim(
        win,
        name="block_end_label",
        text="",
        font="Open Sans",
        pos=(0, 0.1),
        height=s.text_size,
        color=s.text_color,
    )
    S["blk_end_reward"] = visual.TextStim(
        win,
        name="block_end_reward",
        text="",
        font=s.font,
        pos=(0, 0),
        height=s.text_size,
        color=s.text_color,
    )
    S["pause"] = visual.TextStim(
        win,
        name="pause",
        text="If you wish, you can now take a short break.\n",
        font=s.font,
        pos=(0, -0.2),
        height=s.text_size,
        color=s.text_color,
    )
    S["continue"] = visual.TextStim(
        win,
        name="continue",
        text="Press any key to continue.",
        font=s.font,
        pos=(0, -0.43),
        height=s.text_size,
        wrapWidth=1.5,
        color=s.text_color,
    )
    S["fps_warn"] = visual.TextStim(
        win,
        name="fps_warn",
        text="",
        font=s.font,
        pos=(0, 0),
        height=s.text_size,
        wrapWidth=1.5,
        color="red",
    )


    # --- experiment end ------------------------------------------------- #
    S["exp_end"] = visual.TextStim(
        win,
        name="expermiment_end",
        text=(
            "Well done. You completed this task.\n"
            "Your total reward for saving the world is:\n\n\n\n\n"
            "Take a break."
        ),
        font=s.font,
        pos=(0, 0),
        height=s.text_size,
        color=s.text_color,
    )
    S["final_reward"] = visual.TextStim(
        win,
        name="final_reward",
        text="",
        font=s.font,
        pos=(0, 0),
        height=s.text_size,
        color=s.text_color,
    )

    # --- trial components ---------------------------------------------- #
    S["harmless"] = visual.ShapeStim(
        win,
        name="harmless",
        size=s.harmless_area_size,
        vertices="circle",
        pos=s.center_pos,
        lineColor=s.harmless_area_color,
        fillColor=s.harmless_area_color,
    )

    S["shield"] = visual.ShapeStim(
        win,
        name="shield",
        vertices=init_verts,
        size=s.shield_size_outer,
        ori=360,
        pos=s.center_pos,
        lineColor=s.shield_line_color,
        fillColor=s.shield_fill_color,
    )
    S["shield_bg"] = visual.ShapeStim(
        win,
        name="shield_bg",
        vertices=init_verts,
        size=s.shield_size_inner,
        ori=360,
        pos=s.center_pos,
        lineColor=s.harmless_area_color,
        fillColor=s.harmless_area_color,
    )
    S["shield_centre"] = visual.ShapeStim(
        win,
        name="shield_centre",
        vertices=[[0, 0], [0, cfg.circle_radius * 1.21]],
        size=s.shield_size_inner,
        ori=360,
        pos=s.center_pos,
        lineWidth=s.centre_line_width,
        lineColor=s.centre_line_color,
        fillColor=s.centre_line_color,
    )
    S["laser"] = visual.ShapeStim(
        win,
        name="laser",
        vertices=[[0, 0], [0, cfg.circle_radius * s.laser_radius_factor]],
        size=s.shield_size_inner,
        ori=0,
        pos=s.center_pos,
        lineWidth=s.laser_line_width,
        lineColor=s.laser_color,
        fillColor=s.laser_color,
        opacity=0.0,
    )
    S["laser_long"] = visual.ShapeStim(
        win,
        name="laser_long",
        vertices=[[0, 0], [0, cfg.circle_radius * s.laser_long_radius_factor]],
        size=s.shield_size_inner,
        ori=0,
        pos=s.center_pos,
        lineWidth=s.laser_line_width,
        lineColor=s.laser_color,
        fillColor=s.laser_color,
        opacity=0.0,
    )
    S["source"] = visual.ImageStim(
        win,
        name="source",
        image=None,
        pos=s.center_pos,
        size=s.source_size,
    )

    # reward bar
    S["rbar_change"] = visual.Rect(
        win,
        name="reward_bar_change",
        width=s.reward_bar_width,
        height=0.001,
        pos=(s.reward_bar_x, -0.3),
        anchor="bottom-center",
        lineColor="white",
        fillColor="white",
    )
    S["rbar"] = visual.Rect(
        win,
        name="reward_bar",
        width=s.reward_bar_width,
        height=0.5,
        pos=(s.reward_bar_x, -0.05),
        anchor="center",
        lineColor=s.reward_bar_color,
        fillColor=s.reward_bar_color,
    )
    
    # Circular progress indicator uses RadialStim (from psychopy-visionscience,
    # imported lazily so it remains an optional runtime dependency).
    if cfg.round_pbar:
        from psychopy_visionscience.radial import RadialStim
        # Uniform texture overrides RadialStim's default sin-grating so the
        # wedge renders as a solid colour fill.
        _uniform_tex = np.ones((64, 64), dtype=np.float32)

        S["progress_circle"] = RadialStim(
            win,
            name="progress_circle",
            tex=_uniform_tex,
            mask="circle",
            color=cfg.style.progress_bar_color,
            colorSpace="rgb255",      
            radialCycles=0,
            angularCycles=0,
            visibleWedge=(0, 0.001),    # tiny non-zero start (see issue 3)
            size=s.progress_circle_size,
            pos=s.center_pos,
        )
    else:
        S["pbar_edge"] = visual.Rect(
            win,
            name="progress_bar_edge",
            width=s.progress_bar_width,
            height=s.progress_bar_height,
            pos=(0, s.progress_bar_y),
            anchor="center",
            lineWidth=2.0,
            lineColor=s.progress_bar_edge_color,
            fillColor=cfg.background_color,
        )
        S["pbar"] = visual.Rect(
            win,
            name="progress_bar",
            width=0.001,
            height=s.progress_bar_height,
            pos=(-0.4, s.progress_bar_y),
            anchor="center",
            lineColor=s.progress_bar_color,
            fillColor=s.progress_bar_color,
        )
        S["start_lbl"] = visual.TextStim(
            win,
            name="start_label",
            text="Start",
            font=s.font,
            pos=(-0.47, s.progress_bar_y),
            height=s.small_text_size,
            color=s.text_color,
        )
        S["end_lbl"] = visual.TextStim(
            win,
            name="end_label",
            text="End",
            font=s.font,
            pos=(0.47, s.progress_bar_y),
            height=s.small_text_size,
            color=s.text_color,
        )

    S["rtxt_top"] = visual.TextStim(
        win,
        name="reward_text_top",
        text="",
        font=s.font,
        pos=(s.reward_bar_x, 0.25),
        height=s.text_size,
        color=s.text_color,
    )
    S["rtxt_bot"] = visual.TextStim(
        win,
        text="",
        name="reward_text_bottom",
        font=s.font,
        pos=(s.reward_bar_x, -0.35),
        height=s.text_size,
        color=s.text_color,
    )
    

    return S
