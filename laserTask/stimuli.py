from typing import Any, Dict, List, Optional

import numpy as np
from psychopy import visual

from laserTask.config import ExperimentConfig
from psychopy_visionscience.radial import RadialStim

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

# def compute_progress_vertices(
#     progress_degrees: float,
#     circle_radius: float,
#     *,
#     start_angle_deg: float = 0.0,
#     n_points: int = 360,
#     ring_fraction: float = 0.2,   # radial thickness as fraction of circle_radius
# ) -> list:
#     if progress_degrees <= 0:
#         return [[0.0, 0.0]]        # ShapeStim needs ≥1 vertex; kept degenerate

#     inner_r = circle_radius * 1.10
#     outer_r = circle_radius * (1.10 + ring_fraction)

#     start = np.radians(start_angle_deg)
#     end   = np.radians(start_angle_deg + progress_degrees)
#     angles = np.linspace(start, end, n_points)

#     outer = [[float(np.sin(a) * outer_r), float(np.cos(a) * outer_r)] for a in angles]
#     inner = [[float(np.sin(a) * inner_r), float(np.cos(a) * inner_r)] for a in reversed(angles)]

#     return outer + inner
#     # NOTE: Tried to close it explicitly, but that did not help with filling
#     # verts = outer + inner
#     # verts.append(outer[0])
#     # return verts

# NOTE: adapted instructions specifically for Rob, need to make this modular
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

    # Compute sield size vertices for default here
    default_deg = cfg.shield_sizes.default_degrees
    init_verts = compute_shield_vertices(default_deg, cfg.circle_radius)
    # if cfg.round_pbar:
    #     init_progress = compute_progress_vertices(
    #         progress_degrees=1.0,
    #         circle_radius=cfg.circle_radius,
    #     )

    # --- instruction / info screens ------------------------------------ #
    S["title"] = visual.TextStim(
        win,
        name="title",
        #text="Are you ready to save the world?",
        text="Save-the-world task",
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

    # S["title"] = visual.TextBox2(
    #     win, text='Save-the-world task', placeholder='Type here...', font='Open Sans',
    #     pos=(0, 0.35),     letterHeight=0.05,
    #     size=(None, None), borderWidth=2.0,
    #     color='white', colorSpace='rgb',
    #     opacity=None,
    #     bold=True, italic=False,
    #     lineSpacing=1.0, speechPoint=None,
    #     padding=0.0, alignment='center',
    #     anchor='center', overflow='visible',
    #     fillColor=None, borderColor=None,
    #     flipHoriz=False, flipVert=False, languageStyle='LTR',
    #     editable=False,
    #     name='title',
    #     depth=-1, autoLog=True,
    # )
    S["instr1"] = visual.TextStim(
        win,
        name="instr1",
        text=(
            "Welcome to the Save-the-world game!\n\n"
            "Mysterious radioactive sources have just landed on Earth and are emitting radiation that"
            " is harmful to our planet.\n\n"
            "Your task is to catch the radiation beams with an absorbing shield. " 
            "You will have to navigate the shield and position it wisely to minimise the damage "
            "caused by these sources. Help us save the world!"
            "\n\nPress any key to continue."
        ),
        # text=(
        #     "You will now play 1 session of the save-the-world game, "
        #     "where you protect our planet Earth by shielding it from "
        #     "harmful radiation.\n\n"
        #     f"This session will have {n_main_blocks if n_main_blocks is not None else cfg.n_blocks} blocks. "
        #     f"Each block lasts {_dur_str}.\n\n"
        #     f"{_move_blurb}\n\n"
        #     "Pay attention to the different sources and "
        #     "catch as many beams as you can!\n\n"
        #     "Press any key to continue."
        # ),
        font=s.font,
        pos=(0, -0.08),
        height=s.small_text_size,
        wrapWidth=1.5,
        color=s.text_color,
    )

    # Shield instruction only if adjustments allowed
    S["shield_instr"] = visual.TextStim(
        win,
        name="shield_instr",
        text=(
            "Your shield can be positioned anywhere on a circle around the harmful radiation source.\n"
            f"To navigate the shield, press {cfg.key_right.upper()} and {cfg.key_left.upper()} on your {cfg.input_device}. "
            "Try moving the shield now! \n\n"
            "If you have understood how to move the shield, \n"
            f"press {cfg.key_next} to advance to the next screen." 
        ),
        # text=(
        #     build_shield_instructions(cfg, wins_cond)
        #     if cfg.allow_shield_adjustment
        #     else ""
        # ),
        font=s.font,
        pos=(0, 0),
        height=s.small_text_size,
        wrapWidth=1.5,
        color=s.text_color,
    )

    S["reward_instr"] = visual.TextStim(
        win,
        name="reward_instr",
        text=(
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

    S["main_task_instr"] = visual.TextStim(
        win,
        name="main_task_instr",
        text=(
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
    
    # NOTE: This is not a clean implementation
    # It uses a very thick line because I could not get the fillColour to be displayed
    # Next step might be to try RadialStim instead, but that has to be imported from psychopy-visionscience
    if cfg.round_pbar:
        # S["progress_circle"] = visual.ShapeStim(
        #     win,
        #     name="progress_circle",
        #     vertices=init_progress,
        #     size=s.progress_circle_size,
        #     ori=0,
        #     pos=s.center_pos,
        #     lineWidth=s.progress_circle_width,
        #     lineColor=s.progress_bar_color,
        #     #fillColor=s.progress_bar_color,
        #     #closeShape=True,
        # )
        # To show colour properly, need texture = +1 everywhere to replace default sin-grating
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
