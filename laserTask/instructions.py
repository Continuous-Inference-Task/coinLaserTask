"""laserTask.instructions — Plain-text slide instructions.

Every study has one instruction folder (``cfg.instruction_dir``, e.g.
presets/sleps_instructions/). The folder is the complete list of screens:
a section is shown only if its .txt file exists and is non-empty.

  - pre_experiment.txt        (or _loss.txt / _win.txt for framing)
  - pre_practice.txt
  - post_practice.txt
  - pre_main.txt              (split pages with '---', embed images with '@image: path')
  - before_main_block.txt
  - after_main_block.txt
  - post_experiment.txt
  - stop_recording.txt        (required when trigger_mode is 'lsl')

Usage:
  uv run python -m laserTask.instructions --preset presets/SLEPS_default.json
  uv run python -m laserTask.instructions --dir presets/sleps_instructions/ --terminal
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


def build_instruction_context(
    cfg: ExperimentConfig,
    exp_info: Optional[Dict[str, Any]] = None,
    *,
    block_duration_min: float,
    practice_duration_min: float,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Return dictionary of runtime placeholders for text formatting."""
    exp = exp_info or {}
    key_next = cfg.key_next.upper() if cfg.key_next else ""
    def _fmt_min(val: float) -> str:
        return f"{round(val, 1):g} min"

    block_dur_str = _fmt_min(block_duration_min)
    prac_dur_str = _fmt_min(practice_duration_min)

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
    return ctx


# ------------------------------------------------------------------ #
#  Instruction folder                                                 #
# ------------------------------------------------------------------ #

SECTIONS: Tuple[str, ...] = (
    "pre_experiment",
    "pre_practice",
    "post_practice",
    "pre_main",
    "before_main_block",
    "after_main_block",
    "post_experiment",
    "stop_recording",
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_instruction_dir(cfg: ExperimentConfig) -> Path:
    """Return the study's instruction folder; raise if unset or missing."""
    if not cfg.instruction_dir:
        raise ValueError(
            "No instruction folder configured (instruction_dir is empty). "
            "Run 'python wizard.py' and pick one, e.g. presets/peduks_instructions/."
        )
    p = Path(cfg.instruction_dir)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    if not p.is_dir():
        raise FileNotFoundError(f"Instruction folder not found: {p}")
    return p


def read_section_text(section: str, cfg: ExperimentConfig, framing: str) -> str:
    """Raw text of a section ('' if its file is absent or empty).

    ``<section>_<framing>.txt`` takes precedence over ``<section>.txt``.
    """
    folder = resolve_instruction_dir(cfg)
    for f in (folder / f"{section}_{framing}.txt", folder / f"{section}.txt"):
        if f.is_file():
            return f.read_text(encoding="utf-8").strip()
    return ""


def validate_instructions(cfg: ExperimentConfig, framing: str) -> None:
    """Fail before the session starts if the instruction folder is unusable.

    With LSL triggers the stop_recording screen is what keeps the stream
    alive until LabRecorder is stopped, so it must not be missing.
    """
    folder = resolve_instruction_dir(cfg)
    if cfg.trigger_mode == "lsl" and not read_section_text("stop_recording", cfg, framing):
        raise FileNotFoundError(
            f"{folder / 'stop_recording.txt'} is missing or empty. With LSL triggers this screen "
            "holds the stream open until LabRecorder is stopped; add the file before running."
        )


# ------------------------------------------------------------------ #
#  Slide Loader: Splits on '---' and parses '@image:'                #
# ------------------------------------------------------------------ #

def load_section_pages(section: str, cfg: ExperimentConfig, context: Dict[str, Any]) -> List[Tuple[str, List[str]]]:
    """Load (text, [images]) slides for a section. Pages split on '---'.

    Returns [] when the section has no file (or an empty one): no screen.
    """
    raw = read_section_text(section, cfg, context.get("framing", "loss"))
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


IMAGE_TEXT_MARGIN = 0.03  # gap between image row and adjacent text blocks (height units)


def split_text_around_images(text: str) -> Tuple[str, str]:
    """Split slide text into (top, bottom) around the image row.

    The image row goes at the longest run (first on ties) of >=3 consecutive
    blank lines; without such a run everything is placed below the images.
    """
    lines = text.split("\n")
    best_start, best_len, i = -1, 0, 0
    while i < len(lines):
        if lines[i].strip():
            i += 1
            continue
        j = i
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j - i >= 3 and j - i > best_len:
            best_start, best_len = i, j - i
        i = j
    if best_start < 0:
        return "", text
    top = "\n".join(lines[:best_start]).rstrip()
    bottom = "\n".join(lines[best_start + best_len:]).lstrip()
    return top, bottom


def _build_stims(win: Any, text: str, images: List[str], cfg: ExperimentConfig) -> List[Any]:
    """Create PsychoPy visual stimuli for one slide.

    Without images the text is centred. With images the slide is a vertical
    stack [top text] [image row] [bottom text] centred on y=0 (see
    ``split_text_around_images``).
    """
    def make_text(s: str, pos: Tuple[float, float], anchor: str = "center") -> Any:
        return visual.TextStim(win, text=s, font=cfg.style.font, pos=pos, height=cfg.style.small_text_size,
                               wrapWidth=1.5, color=cfg.style.text_color, anchorVert=anchor)

    # (path, size, x) for every image that exists on disk
    row = []
    n = len(images)
    for i, img_path in enumerate(images):
        p = Path(img_path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        if not p.is_file():
            continue
        size, x = (0.2, 0.2), 0.0
        if n == 1:
            try:
                if Image:
                    with Image.open(p) as im: pw, ph = im.size
                    if (pw / ph) > 2.0: size = (0.1 * (pw / ph), 0.1)
            except Exception: pass
        else:
            x = -0.2 + (0.4 * i / (n - 1))
        row.append((p, size, x))

    if not row:
        return [make_text(text, (0, 0))] if text else []

    top, bottom = split_text_around_images(text) if text else ("", "")
    top_stim = make_text(top, (0, 0), "bottom") if top else None
    bottom_stim = make_text(bottom, (0, 0), "top") if bottom else None
    # Rendered text height in height units (boundingBox is in pixels).
    h_top = top_stim.boundingBox[1] / win.size[1] if top_stim else 0.0
    h_bottom = bottom_stim.boundingBox[1] / win.size[1] if bottom_stim else 0.0
    h_img = max(size[1] for _, size, _ in row)
    m = IMAGE_TEXT_MARGIN

    total = h_img + (h_top + m if top_stim else 0.0) + (h_bottom + m if bottom_stim else 0.0)
    y = total / 2  # running top edge
    stims = []
    if top_stim:
        top_stim.pos = (0, y - h_top)
        stims.append(top_stim)
        y -= h_top + m
    y_img = y - h_img / 2
    for p, size, x in row:
        stims.append(visual.ImageStim(win, image=str(p), pos=(x, y_img), size=size, color=[1, 1, 1], colorSpace="rgb", interpolate=True))
    y -= h_img
    if bottom_stim:
        bottom_stim.pos = (0, y - m)
        stims.append(bottom_stim)
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

def _load_preset(cfg: ExperimentConfig, preset: str) -> Dict[str, Any]:
    """Apply a preset's experiment settings to *cfg*; return its stimgen dict."""
    preset_path = Path(preset)
    if not preset_path.is_absolute() and not preset_path.is_file():
        preset_path = _PROJECT_ROOT / preset_path
    preset_data = json.loads(preset_path.read_text(encoding="utf-8"))
    exp_dict = preset_data.get("experiment", {})
    skip_keys = {"dialog_fields", "visits", "sessions", "orders", "framings"}
    for k, v in exp_dict.items():
        if k not in skip_keys and hasattr(cfg, k):
            setattr(cfg, k, tuple(v) if k == "window_size" else v)
    if "n_blocks" in exp_dict:
        cfg.n_blocks = exp_dict["n_blocks"]
    elif isinstance(exp_dict.get("orders"), list):
        cfg.n_blocks = len(exp_dict["orders"])
    cfg.__post_init__()
    return preset_data.get("stimgen", {})


def preview_instructions(
    preset: Optional[str] = None,
    instruction_dir: Optional[str] = None,
    terminal: bool = False,
    screen: Optional[int] = None,
    framing: Optional[str] = None,
) -> None:
    """Open visual window preview (or terminal fallback if headless or requested).

    Settings come from *preset* (a preset JSON) if given, else from the active
    config.json. *instruction_dir* overrides the folder from either source.
    """
    from laserTask.config import get_config
    cfg = get_config()
    if preset:
        stimgen = _load_preset(cfg, preset)
    else:
        from stimgen.laser import config as _stimgen_cfg
        stimgen = {
            "MAIN_BLOCK_DURATION_MIN": _stimgen_cfg.MAIN_BLOCK_DURATION_MIN,
            "PRACTICE_BLOCK_DURATION_MIN": _stimgen_cfg.PRACTICE_BLOCK_DURATION_MIN,
        }
    if instruction_dir:
        cfg.instruction_dir = instruction_dir
    folder = resolve_instruction_dir(cfg)

    if screen is not None:
        cfg.screen_index = screen

    durations = dict(
        block_duration_min=float(stimgen["MAIN_BLOCK_DURATION_MIN"]),
        practice_duration_min=float(stimgen["PRACTICE_BLOCK_DURATION_MIN"]),
    )
    title = folder.name
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
                n_main_blocks=cfg.n_blocks,
                source_img="radioactive1.png",
                **durations,
            )
            for sec in SECTIONS:
                pages = load_section_pages(sec, cfg, ctx)
                for i, (text, images) in enumerate(pages, 1):
                    stims = [banner] + _build_stims(win, text, images, cfg)
                    frm_label = f" ({frm})" if len(framings_to_show) > 1 else ""
                    banner.setText(
                        f"[{title} PREVIEW{frm_label}: {sec} "
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
        print(f"  Instruction Preview: {folder}")
        print("=" * 60)
        for frm in framings_to_show:
            ctx = build_instruction_context(
                cfg,
                exp_info={"framing": frm},
                n_main_blocks=cfg.n_blocks,
                source_img="radioactive1.png",
                **durations,
            )
            if len(framings_to_show) > 1:
                print(f"\n--- Framing: {frm.upper()} ---")
            for sec in SECTIONS:
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
#  Generated placeholder text                                         #
# ------------------------------------------------------------------ #

_TONE_BLURB = (
    "While playing the game, you will also hear tones through your headphones. These tones are completely unrelated to the game. "
    "We are using them to examine how you passively process auditory events. You can ignore the tones and focus on playing the game.\n\n\n"
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preview experiment instructions.")
    parser.add_argument("--preset", "-p", default=None, help="Preset JSON to preview (e.g. presets/SLEPS_default.json); default: active config.json")
    parser.add_argument("--dir", "-d", default=None, help="Instruction folder to preview (overrides the preset's/config's instruction_dir)")
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
        preset=args.preset,
        instruction_dir=args.dir,
        terminal=args.terminal,
        screen=args.screen,
        framing=args.framing,
    )
