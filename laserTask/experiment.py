import os
from itertools import groupby
from pathlib import Path
from typing import List, Optional

import numpy as np
from psychopy import core, data, gui, logging, plugins, visual
from psychopy.hardware import keyboard

plugins.activatePlugins()

from laserTask.audio import AudioStimulationManager
from laserTask.config import TRIGGER_CODES, ExperimentConfig
from laserTask.io import (
    OUTPUT_HEADER,
    build_practice_session_path,
    build_save_path,
    build_session_path,
    load_stimulus_stream,
)
from laserTask.reward import BaseRewardTracker, RewardTracker
from laserTask.stimuli import compute_shield_vertices, create_stimuli
from laserTask.triggers import TriggerManager

_PACKAGE_DIR = Path(__file__).parent
_PROJECT_ROOT = _PACKAGE_DIR.parent


def quit_experiment(
    win: visual.Window,
    trig: TriggerManager,
) -> None:
    """Consistency in exiting the experiment and releasing resources."""
    trig.close()
    win.close()
    core.quit()


def wait_for_key(
    win: visual.Window,
    trig: TriggerManager,  # NOTE: added in case we want to send triggers on instruction screens?
    stimuli: List,
    default_kb: keyboard.Keyboard,
    exp_handler: data.ExperimentHandler,
    min_wait: float = 0.0,
    label: str = "screen",
) -> Optional[str]:
    """Show *stimuli* and block until the participant presses any key.

    Parameters
    ----------
    win          : PsychoPy window.
    stimuli      : Visual components to draw.
    default_kb   : Keyboard used for escape checking.
    exp_handler  : For writing key/RT to the data file.
    min_wait     : Minimum seconds before a response is accepted.
    label        : Name prefix for data columns.

    Returns
    -------
    str or None   Name of the key pressed.
    """
    for stim in stimuli:
        stim.setAutoDraw(True)
    win.flip()

    resp_kb = keyboard.Keyboard()
    clk = core.Clock()
    key_name = None

    while True:
        if clk.getTime() >= min_wait:
            keys = resp_kb.getKeys(waitRelease=False)
            if keys:
                key_name = keys[-1].name
                exp_handler.addData(f"{label}.key", key_name)
                exp_handler.addData(f"{label}.rt", keys[-1].rt)
                break
        if default_kb.getKeys(keyList=["escape"]):
            quit_experiment(win, trig)
        win.flip()

    for stim in stimuli:
        stim.setAutoDraw(False)
    win.flip()
    return key_name


def run_experiment(
    cfg: Optional[ExperimentConfig] = None,
    reward_tracker: Optional[BaseRewardTracker] = None,
    # trigger_manager: Optional[TriggerManager] = None,
) -> None:
    """Entry point — configure, run, and save the Laser Task."""
    # Configuration passed as argument
    # If none provided, fall back to the production defaults
    if cfg is None:
        cfg = ExperimentConfig()

    # ------------------------------------------------------------------ #
    #  PATHS & DIALOG                                                     #
    # ------------------------------------------------------------------ #
    # Paths relative to project root
    root = _PROJECT_ROOT
    os.chdir(root)

    exp_name = "laserTask"

    exp_info = {
        "participant": "000",
        "visit": ["-- select visit --"] + cfg.visits,
        "session": ["-- select session --"] + cfg.sessions,
        "order": ["-- select order --"] + cfg.orders,
        "framing": ["-- select framing --", "loss", "win"],
    }

    while True:
        dlg = gui.DlgFromDict(exp_info, sortKeys=False, title=exp_name)
        if not dlg.OK:
            core.quit()

        if all(
            not str(exp_info[k]).startswith("-- select")
            for k in ["visit", "session", "order", "framing"]
        ):
            break

    exp_info["date"] = data.getDateStr()
    exp_info["expName"] = exp_name

    filename = os.path.join(
        root,
        "data",
        f"{exp_info['participant']}_{exp_name}_{exp_info['date']}",
    )
    the_exp = data.ExperimentHandler(
        name=exp_name,
        extraInfo=exp_info,
        savePickle=True,
        saveWideText=True,
        dataFileName=filename,
    )
    logging.LogFile(filename + ".log", level=logging.EXP)
    # Adapt level for debugging
    logging.console.setLevel(logging.WARNING)

    # ------------------------------------------------------------------ #
    #  WINDOW                                                             #
    # ------------------------------------------------------------------ #
    win = visual.Window(
        size=cfg.window_size,
        fullscr=cfg.fullscreen,
        screen=cfg.screen_index,
        monitor=cfg.monitor_name,
        color=cfg.background_color,
        colorSpace="rgb",
        blendMode="avg",
        useFBO=True,
        units="height",
    )
    win.mouseVisible = False

    # TODO: refresh variable not used again --> check that warning gets sent somewhere if mismatch
    actual_fps = win.getActualFrameRate()
    exp_info["frameRate"] = actual_fps

    # ------------------------------------------------------------------ #
    #  MANAGERS & STIMULI                                                 #
    # ------------------------------------------------------------------ #
    default_kb = keyboard.Keyboard(backend="ptb")
    keys_move = [cfg.key_left, cfg.key_right]
    # Keys for shield size adjustments
    keys_size = (
        [cfg.shield_sizes.key_shrink, cfg.shield_sizes.key_grow]
        if cfg.allow_shield_adjustment
        else []
    )

    trig = TriggerManager(cfg)
    
    audio = AudioStimulationManager(cfg, win, trig)

    session_path = build_session_path(cfg, exp_info)
    save_path = build_save_path(cfg, exp_info)
    main_conditions = data.importConditions(session_path)

    # NOTE: win-loss framing as dropdown in dialog
    wins_condition = 1 if exp_info["framing"] == "win" else 0
    S = create_stimuli(win, cfg, wins_cond=wins_condition, n_main_blocks=len(main_conditions))
    # Reward tracker passed as argument, allowing for easier custom implementations
    if reward_tracker is None:
        reward_tracker = RewardTracker(cfg, wins=wins_condition)

    save_rows: list = [OUTPUT_HEADER]

    PHASE_PRACTICE = 0
    PHASE_MAIN = 1

    block_conditions: list = []

    if cfg.enable_practice:
        practice_session_path = build_practice_session_path(cfg, exp_info)
        practice_conditions = data.importConditions(practice_session_path)
        n_practice = len(practice_conditions)
        for i, _pc in enumerate(practice_conditions):
            _row = dict(_pc)
            _row["phase"] = PHASE_PRACTICE
            _row["phaseBlockIndex"] = i + 1
            _row["phaseBlockTotal"] = n_practice
            _row["toneSeqFileName"] = None
            _row["toneVolatility"] = np.nan
            _row["toneStochasticity"] = np.nan
            block_conditions.append(_row)

    main_block_total = len(main_conditions)
    for _idx, _mc in enumerate(main_conditions, start=1):
        _row = dict(_mc)
        _row["phase"] = PHASE_MAIN
        _row["phaseBlockIndex"] = _idx
        _row["phaseBlockTotal"] = main_block_total
        block_conditions.append(_row)

    # Display warning screen when actual frame rate is not close to 60Hz
    FPS_TOLERANCE = 5
    if actual_fps is None or abs(actual_fps - 60) > FPS_TOLERANCE:
        if actual_fps is None:
            S["fps_warn"].setText(
                "WARNING: Could not detect monitor refresh rate.\n"
                "This experiment is designed for 60 Hz monitors.\n\n"
                "Results may be inaccurate.\n\n"
                "Press any key to continue."
            )
        else:
            S["fps_warn"].setText(
                f"WARNING: Detected refresh rate is {actual_fps:.1f} Hz.\n"
                "This experiment is designed for 60 Hz monitors.\n\n"
                "Results may be inaccurate.\n\n"
                "Press any key to continue."
            )
        wait_for_key(win, trig, [S["fps_warn"]], default_kb, the_exp, label="fps_warn")

    # ------------------------------------------------------------------ #
    #  PRE-LOAD BLOCK STREAMS & LASER DURATION WARNING                   #
    # ------------------------------------------------------------------ #
    # Pre-load all block streams so we can warn about min_laser_duration
    # conflicts before the participant sees any game screens.
    _preloaded_streams: dict = {}
    _laser_warn_blocks: list = []
    min_laser_on = cfg.min_laser_duration_frames

    for _bc in block_conditions:
        _bf = _bc["blockFileName"]
        _stream = load_stimulus_stream(cfg.sequence_root + _bf)
        _preloaded_streams[_bf] = _stream

        _positions = [s[1] for s in _stream]
        _runs = []
        _fi = 0
        for _angle, _group in groupby(_positions):
            _rl = sum(1 for _ in _group)
            _runs.append((_fi, _angle, _rl))
            _fi += _rl

        _actual_min = min(length for _, _, length in _runs)
        if _actual_min <= min_laser_on:
            _phase = int(_bc.get("phase", PHASE_MAIN))
            if _phase == PHASE_PRACTICE:
                _warn_name = "Practice"
            else:
                _warn_name = f"Block {_bc['blockID']}"
            _laser_warn_blocks.append((_warn_name, _actual_min))

    if _laser_warn_blocks:
        _warn_lines = [
            "WARNING: Laser visibility issue detected",
            "",
            f"The laser stays visible for at least {min_laser_on} frames "
            "after appearing.",
            "In the following blocks, the shortest laser run is at or "
            "below this limit,",
            "so the laser will not be hidden during these runs:",
            "",
        ]
        for _warn_name, _min_run in _laser_warn_blocks:
            _warn_lines.append(f"   {_warn_name}: {_min_run} frames")
        _warn_lines += [
            "",
            "Press any key to continue.",
        ]
        S["laser_warn"].setText("\n".join(_warn_lines))
        wait_for_key(
            win, trig, [S["laser_warn"]], default_kb, the_exp, label="laser_warn"
        )
    else:
        logging.debug(
            f"All blocks: Laser visibility limited to {min_laser_on} frames "
            f"(no conflicts with shortest run lengths)."
        )

    trig.send(TRIGGER_CODES["exp_start"])

    # ================================================================== #
    #  GAME INSTRUCTIONS                                                       #
    # ================================================================== #
    wait_for_key(
        win,
        trig,
        [S["title"], S["instr1"]],
        default_kb,
        the_exp,
        label="instr1",
    )
    logging.exp("Participant completed instruction screen 1.")
    the_exp.nextEntry()

    # SCREEN 2 -- Shield-size instructions only if shield adjustments allowed
    if cfg.allow_shield_adjustment:
        wait_for_key(
            win,
            trig,
            [S["shield_instr"]],
            default_kb,
            the_exp,
            label="shield_instr",
        )
        logging.exp("Participant completed instruction screen 2.")
        the_exp.nextEntry()

    # ================================================================== #
    #  BLOCK LOOP                                                         #
    # ================================================================== #
    blocks = data.TrialHandler(
        nReps=1.0,
        method="sequential",
        extraInfo=exp_info,
        trialList=block_conditions,
        seed=None,
        name="blocks_all",
    )
    the_exp.addLoop(blocks)

    entered_main_phase = False

    for bt in blocks:
        # ---- extract condition-file columns explicitly ---------------- #
        phase_n = int(bt.get("phase", PHASE_MAIN))
        phase_block_idx = int(bt.get("phaseBlockIndex", 1))
        phase_block_total = int(bt.get("phaseBlockTotal", cfg.n_blocks))

        if phase_n == PHASE_MAIN and not entered_main_phase:
            if cfg.enable_practice and cfg.reset_reward_after_practice:
                reward_tracker.session_total = 0.0
            wait_for_key(
                win,
                trig,
                [S["main_start"]],
                default_kb,
                the_exp,
                label="main_start",
            )
            entered_main_phase = True

        block_id = bt["blockID"]
        block_file = bt["blockFileName"]
        source_img = bt["sourceImage"]
        volatility = bt.get("volatility", np.nan)
        stochasticity = bt.get("stochasticity", np.nan)
        tone_seq_file = bt.get("toneSeqFileName", None)
        tone_vol = bt.get("toneVolatility", np.nan)
        tone_sto = bt.get("toneStochasticity", np.nan)

        if phase_n == PHASE_PRACTICE:
            # QUESTION: Should practice blocks have background audio (MMN tones)?
            # Currently disabled to reduce cognitive load during learning.
            # If audio should also be practiced, remove this override.
            tone_seq_file = None
            tone_vol = np.nan
            tone_sto = np.nan

        src_path = cfg.image_root + source_img
        earth_path = cfg.image_root + "earth.png"

        # ============================================================== #
        #  BLOCK START SCREEN                                             #
        # ============================================================== #
        trig.send(TRIGGER_CODES["block_start"])

        label = (
            f"Training block {phase_block_idx} out of {phase_block_total}"
            if phase_n == PHASE_PRACTICE
            else f"Block {phase_block_idx} out of {phase_block_total}"
        )
        S["blk_id"].setText(label)
        S["blk_source_img"].setImage(src_path)

        wait_for_key(
            win,
            trig,
            [S["blk_id"], S["blk_start_txt"], S["blk_source_img"]],
            default_kb,
            the_exp,
            label="blk_start",
        )

        # ============================================================== #
        #  TRIAL  (frame-by-frame)                                        #
        # ============================================================== #

        # --- block initialisation -------------------------------------- #
        sds = cfg.shield_sizes
        size_idx = sds.default_index  # reset to middle each block
        sd = sds.size_degrees[size_idx]
        shield_verts = compute_shield_vertices(sd, cfg.circle_radius)
        shield_rot = 360.0  # start at 12 o'clock

        stream = _preloaded_streams[block_file]
        n_frames = len(stream)
        cur_frame = 0

        laser_frame_ct = 0

        # First-hit gate: the extended laser beam is hidden until the
        # first time the shield successfully blocks the laser.
        first_hit_occurred = False
        send_resp_triggers = True

        reward_tracker.reset_block()
        S["source"].setImage(src_path)
        S["earth_background"].setImage(earth_path)

        block_audio_enabled = bool(
            cfg.enable_audio and phase_n == PHASE_MAIN and tone_seq_file
        )
        if block_audio_enabled:
            audio.load_block_sequence(f"{cfg.sequence_root}{tone_seq_file}")

        # Progress bar state
        prog_len = 0.0
        prog_pos = -0.4

        # --- show trial stimuli ---------------------------------------- #
        trial_stims = [
            S["earth_background"],
            S["harmless"],
            S["shield"],
            S["shield_centre"],
            S["shield_bg"],
            S["source"],
            S["rbar_change"],
            S["rbar"],
            S["pbar_edge"],
            S["pbar"],
            S["rtxt_top"],
            S["rtxt_bot"],
            S["start_lbl"],
            S["end_lbl"],
        ]
        for stim in trial_stims:
            stim.setAutoDraw(True)
        S["laser"].setAutoDraw(False)
        S["laser_long"].setAutoDraw(False)

        # For explicit laser duration logging
        laser_on = False
        laser_on_time = None

        # --- frame loop ------------------------------------------------ #
        while cur_frame <= n_frames:
            if default_kb.getKeys(keyList=["escape"]):
                quit_experiment(win, trig)

            if cur_frame >= n_frames:
                trig.send(TRIGGER_CODES["last_frame"])
                break

            # ---- read stimulus ---------------------------------------- #
            true_mean, laser_rot, true_var = stream[cur_frame]

            is_new = cur_frame == 0 or laser_rot != stream[cur_frame - 1][1]
            if is_new:
                laser_frame_ct = 0
            else:
                laser_frame_ct += 1

            # ---- laser visibility ------------------------------------- #
            show_laser = laser_frame_ct <= min_laser_on

            # Explicit laser duration logging for psychopy and csv file
            laser_duration = None
            if show_laser and not laser_on:
                laser_on = True
                laser_on_time = core.getTime()
                logging.exp(f"Laser ON at frame {cur_frame}")
            elif not show_laser and laser_on:
                laser_on = False
                laser_duration = core.getTime() - laser_on_time
                logging.exp(
                    f"Laser OFF at frame {cur_frame} (duration: {laser_duration:.3f}s)"
                )

                # Also save to csv
                # save_rows.append([
                #     "laser_duration", block_id, cur_frame, laser_duration
                # ])

            S["laser"].setAutoDraw(show_laser)
            # Extended beam only appears after the first successful block
            S["laser_long"].setAutoDraw(show_laser and first_hit_occurred)

            # ---- hit detection --------------------------------------- #
            hit = (shield_rot - laser_rot + sd) % 360 <= 2 * sd
            if hit:
                first_hit_occurred = True

            # ---- keyboard input & triggers ---------------------------- #
            trig_val = 0
            do_send = False
            key_released = False
            size_trig_val = 0

            # --- (A) check for shield-size keys  ----------------------- #
            if cfg.allow_shield_adjustment and keys_size:
                size_pressed = default_kb.getKeys(
                    keyList=keys_size,
                    clear=True,
                    waitRelease=False,
                )
                if size_pressed:
                    last_size_key = size_pressed[-1]
                    if (
                        last_size_key.name == sds.key_shrink
                        and size_idx > sds.min_index
                    ):
                        size_idx -= 1
                        size_trig_val = TRIGGER_CODES["shield_shrink"]
                    elif (
                        last_size_key.name == sds.key_grow and size_idx < sds.max_index
                    ):
                        size_idx += 1
                        size_trig_val = TRIGGER_CODES["shield_grow"]
                    sd = sds.size_degrees[size_idx]
                    shield_verts = compute_shield_vertices(sd, cfg.circle_radius)

                    if size_trig_val:
                        trig.send(size_trig_val)

            # --- (B) check for movement keys  --------------------------- #
            released = default_kb.getKeys(
                keyList=keys_move,
                clear=True,
                waitRelease=True,
            )
            if released:
                default_kb.getKeys(
                    keyList=keys_move,
                    clear=True,
                    waitRelease=False,
                )
                trig_val = TRIGGER_CODES["key_release"]
                do_send = True
                key_released = True
            else:
                pressed = default_kb.getKeys(
                    keyList=keys_move,
                    clear=False,
                    waitRelease=False,
                )
                if pressed:
                    last = pressed[-1]
                    if last == cfg.key_right:
                        shield_rot += cfg.rotation_speed
                        new_tv = TRIGGER_CODES["key_right"]
                    else:
                        shield_rot -= cfg.rotation_speed
                        new_tv = TRIGGER_CODES["key_left"]
                    if send_resp_triggers:
                        trig_val = new_tv
                        do_send = True
                        send_resp_triggers = False

            # --- (C) stimulus-change trigger (if nothing else sent) -- #
            if is_new and not do_send:
                trig_val = (
                    TRIGGER_CODES["laser_hit"] if hit else TRIGGER_CODES["laser_miss"]
                )
                do_send = True

            if key_released:
                send_resp_triggers = True

            # ---- reward ----------------------------------------------- #
            reward_tracker.update(hit, is_new, size_index=size_idx)

            # ---- update visuals --------------------------------------- #
            shield_verts = compute_shield_vertices(sd, cfg.circle_radius)

            if hit:
                s_col = cfg.style.shield_hit_color
                ll_opacity = 0.0
            else:
                s_col = cfg.style.shield_fill_color
                ll_opacity = 1.0

            S["shield"].setOri(shield_rot, log=False)
            S["shield"].setVertices(shield_verts, log=False)
            S["shield"].setFillColor(s_col, log=False)
            S["shield"].setLineColor(
                cfg.style.shield_line_color,
                log=False,
            )

            S["shield_bg"].setOri(shield_rot, log=False)
            S["shield_bg"].setVertices(shield_verts, log=False)

            S["shield_centre"].setOri(shield_rot, log=False)
            S["shield_centre"].setVertices(
                [[0, 0], [0, cfg.circle_radius * 1.2]],
                log=False,
            )

            cr = cfg.circle_radius
            S["laser"].setOri(laser_rot, log=False)
            S["laser"].setVertices(
                [[0, 0], [0, cr * cfg.style.laser_radius_factor]],
                log=False,
            )
            S["laser_long"].setOri(laser_rot, log=False)
            S["laser_long"].setOpacity(ll_opacity, log=False)
            S["laser_long"].setVertices(
                [[0, 0], [0, cr * cfg.style.laser_long_radius_factor]],
                log=False,
            )

            S["rbar"].setPos(
                (cfg.style.reward_bar_x, reward_tracker.bar_position),
                log=False,
            )
            S["rbar"].setSize(
                (cfg.style.reward_bar_width, reward_tracker.bar_length),
                log=False,
            )
            S["rbar_change"].setPos(
                (
                    cfg.style.reward_bar_x,
                    reward_tracker.BAR_BOTTOM + reward_tracker.bar_length,
                ),
                log=False,
            )
            S["rbar_change"].setSize(
                (cfg.style.reward_bar_width, reward_tracker.red_bar_length),
                log=False,
            )
            S["rbar_change"].setFillColor(reward_tracker.change_color, log=False)
            S["rbar_change"].setLineColor(reward_tracker.change_color, log=False)

            S["rtxt_top"].setText(reward_tracker.top_text, log=False)
            S["rtxt_bot"].setText(reward_tracker.bottom_text, log=False)

            prog_len += cfg.style.progress_bar_width / n_frames
            prog_pos += 0.4 / n_frames
            S["pbar"].setPos(
                (prog_pos, cfg.style.progress_bar_y),
                log=False,
            )
            S["pbar"].setSize(
                (prog_len, cfg.style.progress_bar_height),
                log=False,
            )

            # ---- triggers --------------------------------------------- #
            if do_send:
                trig.send(trig_val)

            # ---- audio ------------------------------------------------ #
            tone_trig = audio.update_frame() if block_audio_enabled else 0

            # ---- save ------------------------------------------------- #
            save_rows.append(
                [
                    phase_n,
                    block_id,
                    cur_frame,
                    laser_rot,
                    laser_duration,
                    shield_rot,
                    sd,
                    size_idx,
                    int(hit),
                    reward_tracker.total,
                    int(do_send),
                    trig_val,
                    size_trig_val,
                    true_mean,
                    true_var,
                    volatility,
                    stochasticity,
                    tone_trig,
                    tone_vol,
                    tone_sto,
                ]
            )

            cur_frame += 1
            win.flip()

        # --- end trial ------------------------------------------------- #
        for stim in trial_stims:
            stim.setAutoDraw(False)
        S["laser"].setAutoDraw(False)
        S["laser_long"].setAutoDraw(False)

        reward_tracker.end_block()
        np.savetxt(save_path, save_rows, delimiter=",", fmt="%s")
        audio.stop()

        # ============================================================== #
        #  BLOCK END SCREEN                                               #
        # ============================================================== #
        trig.send(TRIGGER_CODES["block_end"])

        if phase_n == PHASE_PRACTICE:
            S["blk_end_label"].setText(
                "Well done, you have finished this practice block!"
            )
            S["blk_end_reward"].setText("")
        else:
            S["blk_end_label"].setText("Well done. In this block, you earned:")
            S["blk_end_reward"].setText(reward_tracker.reward_text)

        wait_for_key(
            win,
            trig,
            [S["blk_end_label"], S["blk_end_reward"], S["pause"], S["continue"]],
            default_kb,
            the_exp,
            min_wait=5.0,
            label="blk_end",
        )
        the_exp.nextEntry()

    # ================================================================== #
    #  EXPERIMENT END                                                     #
    # ================================================================== #
    trig.send(TRIGGER_CODES["exp_end"])

    S["final_reward"].setText(reward_tracker.session_total_text)
    S["exp_end"].setAutoDraw(True)
    S["final_reward"].setAutoDraw(True)

    end_clk = core.Clock()
    while end_clk.getTime() < 5.0:
        if default_kb.getKeys(keyList=["escape"]):
            break
        win.flip()

    S["exp_end"].setAutoDraw(False)
    S["final_reward"].setAutoDraw(False)

    # ------------------------------------------------------------------ #
    #  CLEANUP                                                            #
    # ------------------------------------------------------------------ #
    win.flip()
    the_exp.saveAsWideText(filename + ".csv", delim="auto")
    the_exp.saveAsPickle(filename)
    logging.flush()
    the_exp.abort()
    quit_experiment(win, trig)
