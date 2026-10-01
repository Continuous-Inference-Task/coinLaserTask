"""laserTask.instructions — Plain-text slide instructions (Option 1).

Sections are simple .txt files in your preset folder (e.g. presets/cogpsy_instructions/):
  - pre_experiment.txt        (or _loss.txt / _win.txt for framing)
  - pre_main.txt              (split pages with '---', embed images with '@image: path')
  - pre_practice.txt
  - before_main_block.txt
  - after_main_block.txt
  - post_experiment.txt
  - stop_recording.txt

Usage:
  uv run python -m laserTask.instructions --profile cogpsy
"""

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from PIL import Image
    from psychopy import core, visual, monitors
    from psychopy.hardware import keyboard
except Exception:
    Image = core = visual = monitors = keyboard = None

from laserTask.config import ExperimentConfig


# ------------------------------------------------------------------ #
#  Context Placeholders                                              #
# ------------------------------------------------------------------ #

def _shield_instructions_text(cfg: ExperimentConfig, framing: str, continue_prompt: str) -> str:
    """Participant-facing explanation of shield-size keys and their reward consequences."""
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

    labels: List[str] = []
    for i, sz in enumerate(sds.sizes):
        tag = " (smallest)" if i == 0 else " (largest)" if i == n - 1 else ""
        labels.append(f"{sz.degrees:.0f}°{tag}")

    outcomes = [size.win if framing == "win" else size.loss for size in sds.sizes]
    consequence = "\n".join(
        f"  • {lbl}:  {_event_text(o.hit.total)}" for lbl, o in zip(labels, outcomes)
    )
    miss_values = [o.miss.total for o in outcomes]
    hint = (
        "A smaller shield is harder to aim but earns you more when you succeed!"
        if framing == "win"
        else "A smaller shield is harder to aim but protects your score better!"
    )
    if len(set(miss_values)) == 1:
        miss_line = f"{_miss_text(miss_values[0])} This is the same for all shield sizes."
    else:
        miss_line = "Miss outcome by shield size:\n" + "\n".join(
            f"  • {lbl}: {_miss_text(total).replace('When you miss a beam, ', '')}"
            for lbl, total in zip(labels, miss_values)
        )

    if cfg.input_device == "keyboard":
        shield_blurb = (
            f"Press  '{sds.key_shrink.upper()}'  to make the shield SMALLER.\n"
            f"Press  '{sds.key_grow.upper()}'  to make the shield LARGER.\n\n"
        )
    else:
        shield_blurb = "Use the second response box to make the shield smaller or larger.\n\n"

    return (
        "Shield Size\n\n"
        f"{shield_blurb}"
        f"There are {n} sizes.  Each block starts at the default size ({sds.default_degrees:.0f}°).\n\n"
        f"{hint}\n\n"
        f"Reward by shield size:\n{consequence}\n\n"
        f"{miss_line}\n\n"
        f"{continue_prompt}"
    )


def build_instruction_context(cfg: ExperimentConfig, exp_info: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    """Return dictionary of runtime placeholders for text formatting."""
    exp = exp_info or {}
    key_next = cfg.key_next.upper() if cfg.key_next else ""
    def _fmt_min(val: Any) -> str:
        return f"{round(val, 1):g} min" if isinstance(val, (int, float)) else str(val)

    block_dur_str = _fmt_min(kwargs.get("block_duration_min", 4.0))
    prac_dur_str = _fmt_min(
        kwargs.get(
            "practice_duration_min",
            kwargs.get(
                "practice_block_duration_min",
                1.0 if cfg.instruction_profile == "default" else 2.0,
            ),
        )
    )

    ctx = {
        "key_left": cfg.key_left.upper(),
        "key_right": cfg.key_right.upper(),
        "key_next": key_next or "SPACE",
        "continue_prompt": f"Press '{key_next}' to continue." if key_next else "Press any key to continue.",
        "start_prompt": f"Press '{key_next}' to start." if key_next else "Press any key to start.",
        "move_blurb": (
            f"Use the '{cfg.key_left.upper()}' key to move the shield left "
            f"and the '{cfg.key_right.upper()}' key to move it right."
            if cfg.input_device == "keyboard"
            else "Use the left and right hand-held button keys to navigate the shield."
        ),
        "currency": cfg.currency_symbol,
        "initial_reward": f"{cfg.initial_reward:.2f}",
        "loss_factor": f"{cfg.loss_factor:.3f}",
        "n_main_blocks": kwargs.get("n_main_blocks", cfg.n_blocks),
        "block_duration_min": block_dur_str,
        "practice_duration_min": prac_dur_str,
        "phase_block_idx": kwargs.get("phase_block_idx", 1),
        "phase_block_total": kwargs.get("phase_block_total", cfg.n_blocks),
        "block_reward": kwargs.get("block_reward", f"{cfg.currency_symbol}0.00"),
        "total_reward": kwargs.get("total_reward", f"{cfg.currency_symbol}0.00"),
        "framing": exp.get("framing", "loss"),
        "tone_blurb": _TONE_BLURB if cfg.enable_audio else "",
    }
    ctx["shield_instructions"] = (
        _shield_instructions_text(cfg, ctx["framing"], ctx["continue_prompt"])
        if cfg.allow_shield_adjustment
        else ""
    )
    if kwargs.get("source_img"):
        src = str(kwargs["source_img"]).strip()
        if src:
            if src.startswith(cfg.image_root):
                ctx["source_image_path"] = src
            else:
                ctx["source_image_path"] = f"{cfg.image_root}{src}"
    ctx.update(kwargs)
    ctx["block_duration_min"] = block_dur_str
    ctx["practice_duration_min"] = prac_dur_str
    return ctx


# ------------------------------------------------------------------ #
#  Slide Loader: Splits on '---' and parses '@image:'                #
# ------------------------------------------------------------------ #

def load_section_pages(section: str, cfg: ExperimentConfig, context: Dict[str, Any]) -> List[Tuple[str, List[str]]]:
    """Load (text, [images]) slides for a section. Pages split on '---'."""
    raw = ""
    if cfg.instruction_override_dir:
        p = Path(cfg.instruction_override_dir)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        framing = context.get("framing", "loss")
        for f in (p / f"{section}_{framing}.txt", p / f"{section}.txt"):
            if f.is_file():
                raw = f.read_text(encoding="utf-8").strip()
                break

    if not raw:
        raw = _DEFAULT_PEDUKS.get(section, "")
    if not raw:
        return []

    slides: List[Tuple[str, List[str]]] = []
    for chunk in raw.split("\n---\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        images: List[str] = []
        text_lines: List[str] = []
        for line in chunk.splitlines():
            if line.strip().startswith("@image:"):
                images.extend(img.strip() for img in line.strip().replace("@image:", "").split(",") if img.strip())
            else:
                text_lines.append(line)
        if (
            section == "before_main_block"
            and not images
            and context.get("source_image_path")
            and context["source_image_path"] != cfg.image_root
        ):
            images.append(context["source_image_path"])

        try:
            class _Safe(dict):
                def __missing__(self, k): return f"{{{k}}}"
            body = "\n".join(text_lines).strip().format_map(_Safe(context))
        except Exception:
            body = "\n".join(text_lines).strip()
        if body or images:
            slides.append((body, images))

    return slides


# ------------------------------------------------------------------ #
#  Screen Presentation                                               #
# ------------------------------------------------------------------ #

def show_instruction_section(
    section: str,
    win: Any,
    trig: Any,
    default_kb: Any,
    the_exp: Any,
    cfg: ExperimentConfig,
    context: Dict[str, Any],
    quit_callback: Optional[Callable[[], None]] = None,
) -> None:
    """Present all slides for a lifecycle section."""
    pages = load_section_pages(section, cfg, context)
    if not pages:
        return

    allowed = [cfg.key_next] if cfg.key_next else None

    for i, (text, images) in enumerate(pages, 1):
        stims = _build_stims(win, text, images, cfg)
        label = f"{section}_{i}"

        if section == "post_experiment":
            _show_timed(win, stims, default_kb, duration=5.0, quit_callback=quit_callback)
        elif section == "stop_recording":
            _show_wait(win, stims, default_kb, the_exp, label, ["return"], 0.0, quit_callback)
            if the_exp is not None:
                the_exp.nextEntry()
        else:
            min_wait = 5.0 if section == "after_main_block" else 0.0
            _show_wait(win, stims, default_kb, the_exp, label, allowed, min_wait, quit_callback)
            if section == "pre_experiment" and the_exp is not None:
                the_exp.nextEntry()


def _build_stims(win: Any, text: str, images: List[str], cfg: ExperimentConfig) -> List[Any]:
    """Create PsychoPy visual stimuli for one slide."""
    stims = []
    if text:
        pos = (0, -0.08) if images else (0, 0)
        stims.append(visual.TextStim(win, text=text, font=cfg.style.font, pos=pos, height=cfg.style.small_text_size, wrapWidth=1.5, color=cfg.style.text_color))

    n = len(images)
    for i, img_path in enumerate(images):
        p = Path(img_path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        if not p.is_file():
            continue
        size, pos = (0.2, 0.2), (0.0, 0.11)
        if n == 1:
            try:
                if Image:
                    with Image.open(p) as im: pw, ph = im.size
                    if (pw / ph) > 2.0: size = (0.1 * (pw / ph), 0.1)
            except Exception: pass
        else:
            pos = (-0.2 + (0.4 * i / (n - 1)), 0.11)
        stims.append(visual.ImageStim(win, image=str(p), pos=pos, size=size, color=[1, 1, 1], colorSpace="rgb", interpolate=True))

    return stims


def _show_wait(win: Any, stims: List[Any], kb: Any, the_exp: Any, label: str, allowed: Optional[List[str]], min_wait: float, quit_callback: Optional[Callable[[], None]]) -> None:
    for s in stims: s.setAutoDraw(True)
    win.flip()
    kb.clearEvents()
    clk = core.Clock()
    while True:
        if clk.getTime() >= min_wait:
            keys = kb.getKeys(keyList=allowed, waitRelease=False)
            if keys:
                if the_exp is not None and label:
                    the_exp.addData(f"{label}.key", keys[-1].name)
                    the_exp.addData(f"{label}.rt", keys[-1].rt)
                break
        if kb.getKeys(keyList=["escape"]):
            quit_callback() if quit_callback else core.quit()
        win.flip()
    for s in stims: s.setAutoDraw(False)
    win.flip()


def _show_timed(win: Any, stims: List[Any], kb: Any, duration: float = 5.0, quit_callback: Optional[Callable[[], None]] = None) -> None:
    for s in stims: s.setAutoDraw(True)
    win.flip()
    clk = core.Clock()
    while clk.getTime() < duration:
        if kb.getKeys(keyList=["escape"]): break
        win.flip()
    for s in stims: s.setAutoDraw(False)
    win.flip()


# ------------------------------------------------------------------ #
#  CLI Preview Tool                                                  #
# ------------------------------------------------------------------ #

_PRESET_BY_PROFILE = {
    "sleps": "presets/SLEPS_default.json",
    "cogpsy": "presets/Cogpsy_Rob_Version_2026.json",
}


def preview_instructions(
    profile: Optional[str] = None,
    terminal: bool = False,
    screen: Optional[int] = None,
    framing: Optional[str] = None,
) -> None:
    """Open visual window preview (or terminal fallback if headless or requested)."""
    from laserTask.config import get_config
    cfg = get_config()
    if profile:
        cfg.instruction_profile = profile
        cfg.instruction_override_dir = f"presets/{profile}_instructions/" if profile in ("cogpsy", "sleps") else ""

    preset_n_blocks = None
    if profile in _PRESET_BY_PROFILE:
        preset_rel = _PRESET_BY_PROFILE[profile]
        repo_root = Path(__file__).resolve().parent.parent
        preset_path = repo_root / preset_rel
        if not preset_path.is_file() and Path(preset_rel).is_file():
            preset_path = Path(preset_rel)

        if preset_path.is_file():
            try:
                with open(preset_path, "r", encoding="utf-8") as fh:
                    preset_data = json.load(fh)
                exp_dict = preset_data.get("experiment", {})
                skip_keys = {
                    "instruction_profile",
                    "instruction_override_dir",
                    "dialog_fields",
                    "visits",
                    "sessions",
                    "orders",
                    "framings",
                }
                for k, v in exp_dict.items():
                    if k not in skip_keys and hasattr(cfg, k):
                        setattr(cfg, k, v)
                if "n_blocks" in exp_dict:
                    preset_n_blocks = exp_dict["n_blocks"]
                elif "orders" in exp_dict and isinstance(exp_dict["orders"], list):
                    preset_n_blocks = len(exp_dict["orders"])
                if preset_n_blocks:
                    cfg.n_blocks = preset_n_blocks
            except Exception as err:
                print(f"Warning: could not load preset {preset_path}: {err}")
        else:
            print(f"Warning: preset file {preset_path} not found; using active config.")

    if screen is not None:
        cfg.screen_index = screen

    n_blocks_val = preset_n_blocks or cfg.n_blocks
    sections = [
        "pre_experiment",
        "pre_practice",
        "post_practice",
        "pre_main",
        "before_main_block",
        "after_main_block",
        "post_experiment",
        "stop_recording",
    ]
    framings_to_show = [framing] if framing else ["loss", "win"]

    # Standard PsychoPy window creation (matches laserTask/experiment.py)
    try:
        if terminal:
            raise RuntimeError("Terminal output requested via --terminal")

        if visual is None:
            try:
                import wx
            except Exception:
                import sys
                from unittest.mock import MagicMock
                sys.modules.setdefault("wx", MagicMock())
            from psychopy import core as _c, visual as _v, monitors as _m
            from psychopy.hardware import keyboard as _k
            globals().update(core=_c, visual=_v, monitors=_m, keyboard=_k)
        if monitors and cfg.monitor_name not in monitors.getAllMonitors():
            try:
                mon = monitors.Monitor(cfg.monitor_name, width=53.0, distance=60.0)
                mon.setSizePix(cfg.window_size)
                mon.save()
            except Exception:
                pass

        win = visual.Window(
            size=(1280, 800),
            fullscr=False,
            screen=cfg.screen_index,
            monitor=cfg.monitor_name,
            color=cfg.background_color,
            colorSpace="rgb",
            blendMode="avg",
            useFBO=True,
            units="height",
        )
        backend = cfg.keyboard_backend or ("ptb" if sys.platform == "win32" else "event")
        kb = keyboard.Keyboard(backend=backend)
        banner = visual.TextStim(win, text="", pos=(0, 0.44), height=0.025, color="yellow")

        quit_req = False
        for frm in framings_to_show:
            ctx = build_instruction_context(
                cfg,
                exp_info={"framing": frm},
                n_main_blocks=n_blocks_val,
                block_duration_min=4.0,
                source_img="radioactive1.png",
            )
            for sec in sections:
                pages = load_section_pages(sec, cfg, ctx)
                for i, (text, images) in enumerate(pages, 1):
                    stims = [banner] + _build_stims(win, text, images, cfg)
                    frm_label = f" ({frm})" if len(framings_to_show) > 1 else ""
                    banner.setText(
                        f"[{cfg.instruction_profile.upper()} PREVIEW{frm_label}: {sec} "
                        f"(Page {i}/{len(pages)}) | Press SPACE to advance, ESC to quit]"
                    )
                    for s in stims:
                        s.setAutoDraw(True)
                    win.flip()
                    kb.clearEvents()
                    while True:
                        keys = kb.getKeys(waitRelease=False)
                        if any(k.name == "escape" for k in keys):
                            quit_req = True
                            break
                        if keys:
                            break
                        win.flip()
                    for s in stims:
                        s.setAutoDraw(False)
                    win.flip()
                    if quit_req:
                        break
                if quit_req:
                    break
            if quit_req:
                break
        win.close()
        print("Visual preview finished.")
    except Exception as exc:
        print(f"(No graphical display: {exc} — showing text preview)\n")
        print("=" * 60)
        print(f"  Instruction Preview: Profile '{cfg.instruction_profile}'")
        print("=" * 60)
        for frm in framings_to_show:
            ctx = build_instruction_context(
                cfg,
                exp_info={"framing": frm},
                n_main_blocks=n_blocks_val,
                block_duration_min=4.0,
                source_img="radioactive1.png",
            )
            if len(framings_to_show) > 1:
                print(f"\n--- Framing: {frm.upper()} ---")
            for sec in sections:
                pages = load_section_pages(sec, cfg, ctx)
                if not pages:
                    continue
                print(f"\n[{sec}] ({len(pages)} page(s))")
                for i, (t, imgs) in enumerate(pages, 1):
                    print(f"  ── Page {i}/{len(pages)} ──")
                    if imgs:
                        print(f"     Images: {', '.join(imgs)}")
                    for line in t.splitlines():
                        print(f"     {line}")
                    print()

# ------------------------------------------------------------------ #
#  Default PEDUKS Text Dictionary                                    #
# ------------------------------------------------------------------ #

_TONE_BLURB = (
    "While playing the game, you will also hear tones through your headphones. These tones are completely unrelated to the game. "
    "We are using them to examine how you passively process auditory events. You can ignore the tones and focus on playing the game.\n\n\n"
)

_DEFAULT_PEDUKS: Dict[str, str] = {
    "pre_experiment": (
        "Are you ready to save the world?\n\n"
        "You will now play 1 session of the save-the-world game, "
        "where you protect our planet Earth by shielding it from harmful radiation.\n\n"
        "This session will have {n_main_blocks} blocks. Each block lasts {block_duration_min}.\n\n"
        "{move_blurb}\n\n"
        "Pay attention to the different sources and catch as many beams as you can!\n\n"
        "{continue_prompt}\n"
        "---\n"
        "{shield_instructions}"
    ),
    "pre_practice": (
        "You will now do a short practice block of the task. This block will last {practice_duration_min}.\n\n"
        "As in the real game, the source will emit radiation, but the main angle of attack might change over time, "
        "so that you have to keep monitoring the beams and decide when to re-position your shield.\n\n"
        "You will see a reward bar on the right of the screen, which shows you how you lose money whenever a beam "
        "remains uncaught, but you will not actually earn any money during this practice. "
        "Remember to use the '{key_left}' and '{key_right}' keys to navigate your shield.\n\n"
        "{start_prompt}"
    ),
    "post_practice": (
        "Well done - this was the practice block!\n\n"
        "As you have seen, the direction of the beams can jump around quickly, and you cannot catch all beams with your shield. "
        "That's ok - just try to catch as many as possible. The source will have a main direction of attack at any point - "
        "if you place your shield in that direction, you will catch most beams.\n\n"
        "Moving your shield also costs energy, which will be subtracted from your reward. It is thus important that you only move "
        "your shield when you think that the main direction of attack has changed.\n\n"
        "{continue_prompt}"
    ),
    "pre_main": (
        "{tone_blurb}{start_prompt}"
    ),
    "before_main_block": (
        "Block {phase_block_idx} out of {phase_block_total}\n\n"
        "New source ahead:\n\n\n\n\n\n\n\n\n"
        "!!Please try to keep your eyes focussed on the source throughout the block!!\n\n"
        "{start_prompt}"
    ),
    "after_main_block": (
        "Well done. In this block, you earned:\n\n"
        "{block_reward}\n\n\n"
        "If you wish, you can now take a short break.\n\n"
        "{continue_prompt}"
    ),
    "post_experiment": (
        "Well done. You completed all blocks of this session.\n\n"
        "In this session, you have earned:\n\n"
        "{total_reward}\n\n\n"
        "Thank you"
    ),
    "stop_recording": (
        "Please STOP the recording in LabRecorder now.\n\n"
        "Once recording has stopped, press ENTER to finish."
    ),
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preview experiment instructions.")
    parser.add_argument("--profile", "-p", choices=["default", "cogpsy", "sleps"], help="Profile to preview")
    parser.add_argument("--screen", "-s", type=int, default=None, help="Target screen index (0, 1, ...)")
    parser.add_argument("--terminal", "-t", action="store_true", help="Print instructions in terminal instead of opening a window")
    parser.add_argument(
        "--framing",
        "-F",
        choices=["loss", "win"],
        default=None,
        help="Framing variant to preview (loss or win; default previews both)",
    )
    args = parser.parse_args()
    preview_instructions(
        args.profile,
        terminal=args.terminal,
        screen=args.screen,
        framing=args.framing,
    )
