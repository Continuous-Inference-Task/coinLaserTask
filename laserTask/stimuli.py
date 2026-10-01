from typing import Any, Dict

import numpy as np
from psychopy import visual

from laserTask.config import ExperimentConfig

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

def create_stimuli(
    win: visual.Window,
    cfg: ExperimentConfig,
) -> Dict[str, Any]:
    """Instantiate every ``visual.*`` component used by the experiment.

    Appearance is governed entirely by ``cfg.style``.  To change how
    anything looks, edit ``StimulusStyle`` — not this function.

    Returns
    -------
    dict  str → PsychoPy stimulus
    """
    s = cfg.style  # shorthand
    S: Dict[str, Any] = {}

    # Compute sield size vertices for default here
    default_deg = cfg.shield_sizes.default_degrees
    init_verts = compute_shield_vertices(default_deg, cfg.circle_radius)

    # Warning screen for non-60Hz monitors
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

    # --- trial components ---------------------------------------------- #
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
        vertices=[[0, 0], [0, cfg.circle_radius * 1.2]],
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
    if cfg.round_pbar:
        try:
            from psychopy_visionscience.radial import RadialStim
        except ImportError:
            from psychopy.visual import RadialStim
        _uniform_tex = np.ones((64, 64), dtype=np.float32)
        pbar_col = cfg.style.progress_bar_color
        if isinstance(pbar_col, (list, tuple)):
            pbar_col_space = "rgb255" if any(v > 1.0 for v in pbar_col) else "rgb"
        else:
            pbar_col_space = "named"
        S["progress_circle"] = RadialStim(
            win,
            name="progress_circle",
            tex=_uniform_tex,
            mask="circle",
            color=pbar_col,
            colorSpace=pbar_col_space,
            radialCycles=0,
            angularCycles=0,
            visibleWedge=(0, 0.001),
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

    if not cfg.show_source:
        S["reward_center"] = visual.TextStim(
            win,
            name="reward_center",
            text="",
            font=s.font,
            pos=(0, -0.025),
            height=s.text_size * 0.6,
            color=s.text_color,
        )


    return S
