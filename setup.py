#!/usr/bin/env python3
"""
setup.py — Modern CLI onboarding & configuration wizard for the CoIn Laser Task.

Walks you through machine setup, experiment design, shield/reward parameters,
auditory MMN settings, and sequence generation.  You can configure everything
at once or pick individual sections.

Usage:
    python setup.py              # interactive menu
    python setup.py --full       # straight into full wizard (all sections)
    python setup.py --report     # print current config without prompts
    python setup.py --generate   # just regenerate sequences from current config
    python setup.py --help       # show this message

No dependencies beyond Python stdlib.  Works over SSH, in tmux, anywhere.
"""

from __future__ import annotations

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── project root detection ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config_shared import (
        SEQUENCE_VERSION,
        PRACTICE_SEQUENCE_VERSION,
        SEQUENCE_ROOT,
    )
except ImportError:
    print("ERROR: Cannot find config_shared.py — run from project root.")
    sys.exit(1)

# ── minimal terminal helpers (zero dependencies) ────────────────────────────

C = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "magenta": "\033[35m",
    "blue": "\033[34m",
}
_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if _USE_COLOR:
        return f"{code}{text}{C['reset']}"
    return str(text)


def clear() -> None:
    os.system("clear" if os.name != "nt" else "cls")


def header(text: str) -> None:
    width = 57
    line = "─" * (width - 2)
    print()
    print(_c(C["cyan"], f"╭{line}╮"))
    print(_c(C["cyan"], "│") + _c(C["bold"], text.center(width - 2)) + _c(C["cyan"], "│"))
    print(_c(C["cyan"], f"╰{line}╯"))
    print()


def section(text: str) -> None:
    print()
    print(_c(C["yellow"], f"━━━ {text} ") + _c(C["dim"], "─" * (50 - len(text))))
    print()


def info(text: str) -> None:
    print(_c(C["dim"], f"  {text}"))


def hint(text: str) -> None:
    """Dim hint line — for extra context below a prompt."""
    print(_c(C["dim"], f"     {text}"))


def success(text: str) -> None:
    print(_c(C["green"], f"  ✓ {text}"))


def warn(text: str) -> None:
    print(_c(C["yellow"], f"  ⚠ {text}"))


def fail(text: str) -> None:
    print(_c(C["red"], f"  ✗ {text}"))


# ── prompts ─────────────────────────────────────────────────────────────────

def prompt(
    text: str,
    default: str = "",
    *,
    choices: Optional[List[str]] = None,
    hint_text: str = "",
) -> str:
    """Ask the user for input.  Shows default and optional hint below."""
    if choices:
        for i, choice in enumerate(choices, 1):
            marker = _c(C["green"], "→") if choice == default else " "
            print(f"     {marker} {i}. {choice}")
        print()

    default_display = _c(C["dim"], f" [default: {default}]") if default else ""
    if hint_text:
        print(f"  {text}{default_display}:")
        print(_c(C["dim"], f"     {hint_text}"))
        raw = input("  > ").strip()
    else:
        raw = input(f"  {text}{default_display}: ").strip()
    return raw if raw else default


def prompt_yn(text: str, default: bool = True, *, hint_text: str = "") -> bool:
    hint_label = "Y/n" if default else "y/N"
    raw = prompt(f"{text} [{hint_label}]", "", hint_text=hint_text).strip().lower()
    if raw in ("y", "yes"):
        return True
    if raw in ("n", "no"):
        return False
    return default


def prompt_int(
    text: str,
    default: int,
    *,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
    hint_text: str = "",
) -> int:
    while True:
        raw = prompt(text, str(default), hint_text=hint_text)
        try:
            val = int(raw)
            if min_val is not None and val < min_val:
                warn(f"Must be ≥ {min_val}")
                continue
            if max_val is not None and val > max_val:
                warn(f"Must be ≤ {max_val}")
                continue
            return val
        except ValueError:
            warn("Please enter a number.")


def prompt_float(text: str, default: float, *, hint_text: str = "") -> float:
    while True:
        raw = prompt(text, str(default), hint_text=hint_text)
        try:
            return float(raw)
        except ValueError:
            warn("Please enter a number.")


def prompt_list(text: str, default: List[str], *, hint_text: str = "") -> List[str]:
    raw = prompt(text, ",".join(default), hint_text=hint_text)
    return [x.strip() for x in raw.split(",") if x.strip()]


def prompt_multiselect(
    text: str,
    options: List[str],
    defaults: Optional[List[str]] = None,
    *,
    hint_text: str = "",
    action_keys: Optional[Dict[str, str]] = None,
    header_text: Optional[str] = None,
) -> Tuple[List[str], Optional[str]]:
    """Interactive checkbox list — space to toggle, arrows to navigate.

    Uses raw terminal mode on Unix for real-time input.  Falls back to a
    simple numbered-list prompt on platforms without ``termios``.

    Parameters
    ----------
    text :
        Prompt shown above the list.
    options :
        All selectable items.
    defaults :
        Pre-selected items (must be a subset of *options*).
    hint_text :
        Dim explanatory text below the prompt.
    action_keys :
        Extra single-key shortcuts with descriptions, e.g.
        ``{"r": "run experiment", "g": "generate"}``.  When pressed the
        function returns immediately with that key as the second tuple
        element.
    header_text :
        Optional banner title drawn at the very top of every redraw
        (e.g. ``"CoIn Laser Task — Setup"``).

    Returns
    -------
    (selected, action)
        *selected* – items the user chose (in original *options* order).
        *action* – ``None`` if confirmed with Enter, or the action-key
        string if an action key was pressed.
    """
    if defaults is None:
        defaults = []
    selected: List[str] = [o for o in options if o in defaults]

    # ── Unix raw-terminal path ──
    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        cursor = 0

        def _redraw() -> None:
            """Repaint the entire list in-place using ANSI escape codes.
            Works directly on the terminal fd — no subprocess, no cursor
            arithmetic, safe on any terminal width."""
            sys.stdout.write("\033[H\033[2J")
            if header_text:
                width = 57
                bar = "─" * (width - 2)
                sys.stdout.write(
                    _c(C["cyan"], f"\n╭{bar}╮\n")
                    + _c(C["cyan"], "│")
                    + _c(C["bold"], header_text.center(width - 2))
                    + _c(C["cyan"], "│\n")
                    + _c(C["cyan"], f"╰{bar}╯\n\n")
                )
            sys.stdout.write(f"  {text}:\n")
            if hint_text:
                sys.stdout.write(_c(C["dim"], f"     {hint_text}") + "\n")
            sys.stdout.write("\n")
            for i, opt in enumerate(options):
                sel = opt in selected
                mark = _c(C["green"], "[x]") if sel else _c(C["dim"], "[ ]")
                pointer = _c(C["cyan"], " ›") if i == cursor else "  "
                sys.stdout.write(f"  {pointer} {mark} {opt}\n")
            sys.stdout.write("\n")
            # Navigation hints on one line, action keys on another if present.
            nav = f"  {_c(C['dim'], '↑↓/jk')} navigate   {_c(C['dim'], 'space')} toggle   {_c(C['dim'], 'enter')} confirm   {_c(C['dim'], 'a')} all  {_c(C['dim'], 'n')} none"
            sys.stdout.write(nav + "\n")
            if action_keys:
                ak = "   ".join(
                    f"{_c(C['dim'], k)} {v}" for k, v in action_keys.items()
                )
                sys.stdout.write(f"  {ak}\n")
            sys.stdout.flush()

        try:
            tty.setraw(fd)
            _redraw()
            while True:
                ch = sys.stdin.read(1)

                # ── escape sequences (arrows) ──
                if ch == "\x1b":
                    nxt = sys.stdin.read(2)
                    if nxt == "[A":  # up
                        cursor = (cursor - 1) % len(options)
                    elif nxt == "[B":  # down
                        cursor = (cursor + 1) % len(options)

                # ── enter ──
                elif ch in ("\r", "\n"):
                    break

                # ── space ──
                elif ch == " ":
                    opt = options[cursor]
                    if opt in selected:
                        selected.remove(opt)
                    else:
                        selected.append(opt)

                # ── j / k vim keys ──
                elif ch == "j":
                    cursor = (cursor + 1) % len(options)
                elif ch == "k":
                    cursor = (cursor - 1) % len(options)

                # ── a = all, n = none ──
                elif ch == "a":
                    selected = list(options)
                elif ch == "n":
                    selected = []

                # ── action keys ──
                elif action_keys and ch in action_keys:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
                    sys.stdout.write("\033[H\033[2J")
                    sys.stdout.flush()
                    return sorted(selected, key=lambda o: options.index(o)), ch

                _redraw()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

        sys.stdout.write("\033[H\033[2J")
        sys.stdout.flush()
        return sorted(selected, key=lambda o: options.index(o)), None

    except (ImportError, termios.error, AttributeError):
        pass

    # ── fallback: simple numbered prompt ──
    return _prompt_multiselect_fallback(text, options, defaults, hint_text, action_keys)


def _prompt_multiselect_fallback(
    text: str,
    options: List[str],
    defaults: List[str],
    hint_text: str,
    action_keys: Optional[Dict[str, str]],
) -> Tuple[List[str], Optional[str]]:
    """Fallback when raw terminal mode is unavailable (e.g. Windows)."""
    selected = set(defaults)
    while True:
        print(f"\n  {text}:")
        if hint_text:
            print(_c(C["dim"], f"     {hint_text}"))
        for i, opt in enumerate(options, 1):
            mark = _c(C["green"], "[x]") if opt in selected else _c(C["dim"], "[ ]")
            print(f"     {mark} {i}. {opt}")
        print()
        print(_c(C["dim"], "  Enter numbers to toggle (e.g. 3,5), or press Enter to confirm."))
        if action_keys:
            ak = ", ".join(f"'{k}'={v}" for k, v in action_keys.items())
            print(_c(C["dim"], f"  Actions: {ak}, 'a'=all, 'n'=none"))
        raw = input(f"  {_c(C['bold'], '>')} ").strip().lower()

        if not raw:
            return sorted(selected, key=lambda o: options.index(o)), None
        if action_keys and raw in action_keys:
            return sorted(selected, key=lambda o: options.index(o)), raw
        if raw == "a":
            selected = set(options)
            continue
        if raw == "n":
            selected = set()
            continue

        for part in raw.replace(" ", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                idx = int(part) - 1
                if 0 <= idx < len(options):
                    opt = options[idx]
                    if opt in selected:
                        selected.discard(opt)
                    else:
                        selected.add(opt)
            except ValueError:
                pass


# ── config readers / writers ────────────────────────────────────────────────

def _read_laser_task_config() -> Dict[str, Any]:
    """Read laserTask/config.py via direct import."""
    from laserTask.config import ExperimentConfig
    c = ExperimentConfig()
    return {
        "window_size_w": c.window_size[0],
        "window_size_h": c.window_size[1],
        "fullscreen": c.fullscreen,
        "screen_index": c.screen_index,
        "monitor_name": c.monitor_name,
        "target_refresh_rate": c.target_refresh_rate,
        "key_right": c.key_right,
        "key_left": c.key_left,
        "input_device": c.input_device,
        "rotation_speed": c.rotation_speed,
        "circle_radius": c.circle_radius,
        "allow_shield_adjustment": c.allow_shield_adjustment,
        "loss_factor": c.loss_factor,
        "currency_symbol": c.currency_symbol,
        "trigger_mode": c.trigger_mode,
        "serial_port": c.serial_port,
        "serial_baud_rate": c.serial_baud_rate,
        "parallel_address": c.parallel_address,
        "enable_audio": c.enable_audio,
        "tone_freq_standard": c.tone_freq_standard,
        "tone_freq_deviant": c.tone_freq_deviant,
        "tone_duration": c.tone_duration,
        "tone_volume": c.tone_volume,
        "tone_isi_frames": c.tone_isi_frames,
        "enable_practice": c.enable_practice,
        "n_blocks": c.n_blocks,
        "min_laser_duration_frames": c.min_laser_duration_frames,
        "visits": list(c.visits),
        "sessions": list(c.sessions),
        "orders": list(c.orders),
        "framings": list(c.framings),
        "dialog_fields": list(c.dialog_fields),
        "keyboard_backend": c.keyboard_backend,
    }


def _read_stimgen_config() -> Dict[str, Any]:
    """Read stimgen/laser/config.py via direct import (no eval, no regex)."""
    import importlib
    from stimgen.laser import config as _cfg
    importlib.reload(_cfg)  # bust cache so writes are visible
    return {
        "SAMPLE_RATE": _cfg.SAMPLE_RATE,
        "NOISE_STD_LOW": _cfg.NOISE_STD_LOW,
        "NOISE_STD_HIGH": _cfg.NOISE_STD_HIGH,
        "JUMP_DURATION_MEAN_SEC": _cfg.JUMP_DURATION_MEAN_SEC,
        "JUMP_DURATION_MIN_SEC": _cfg.JUMP_DURATION_MIN_SEC,
        "JUMP_DURATION_MAX_SEC": _cfg.JUMP_DURATION_MAX_SEC,
        "JUMP_VALUE_SET": _cfg.JUMP_VALUE_SET,
        "MAIN_SESSION": dict(_cfg.MAIN_SESSION),
        "PRACTICE_SESSION": dict(_cfg.PRACTICE_SESSION),
        "ONLINE_TRAINING_SESSION": dict(_cfg.ONLINE_TRAINING_SESSION),
        "DEFAULT_SESSION": dict(_cfg.DEFAULT_SESSION),
    }


def _save_stimgen_from_cfg(cfg: Dict[str, Any]) -> bool:
    """Write stimgen config if there are pending updates in cfg."""
    stimgen_updates = cfg.pop("_stimgen_updates", None)
    if not stimgen_updates:
        return True

    ms = _read_stimgen_config()
    ms_dict = ms.get("MAIN_SESSION", {})
    ps_dict = ms.get("PRACTICE_SESSION", {})
    ot_dict = ms.get("ONLINE_TRAINING_SESSION", {})

    flat: Dict[str, Any] = {}
    for k, v in stimgen_updates.items():
        if k == "_main_block_dur":
            ms_dict["blockDurationMin"] = v
        elif k == "_main_n_blocks":
            ms_dict["nBlocks"] = v
        elif k == "_practice_block_dur":
            ps_dict["blockDurationMin"] = v
        elif k == "_practice_n_blocks":
            ps_dict["nBlocks"] = v
        elif k == "_online_block_dur":
            ot_dict["blockDurationMin"] = v
        elif k == "_online_n_blocks":
            ot_dict["nBlocks"] = v
        elif not k.startswith("_"):
            flat[k] = v

    if ms_dict:
        flat["MAIN_SESSION"] = ms_dict
    if ps_dict:
        flat["PRACTICE_SESSION"] = ps_dict
    if ot_dict:
        flat["ONLINE_TRAINING_SESSION"] = ot_dict

    try:
        _write_stimgen_config(flat)
        success("stimgen/laser/config.py updated")
        return True
    except Exception as exc:
        fail(f"Could not write stimgen config: {exc}")
        return False


def _write_stimgen_config(updates: Dict[str, Any]) -> None:
    cfg_path = PROJECT_ROOT / "stimgen" / "laser" / "config.py"
    source = cfg_path.read_text()
    for name, value in updates.items():
        if isinstance(value, dict):
            # Multi-line dict — replace entire block from KEY = { … }
            lines = [f"{name} = {{"]
            for dk, dv in value.items():
                if isinstance(dv, str):
                    lines.append(f'    "{dk}": "{dv}",')
                else:
                    lines.append(f'    "{dk}": {dv},')
            lines.append("}")
            replacement = "\n".join(lines)
            source = re.sub(
                rf'^{name}\s*=\s*\{{.*?^\}}',
                replacement,
                source,
                flags=re.MULTILINE | re.DOTALL,
            )
        else:
            py_val = repr(value) if isinstance(value, str) else str(value)
            source = re.sub(
                rf'^({name}\s*=\s*).+?(\s*(?:#.*)?)$',
                rf'\g<1>{py_val}\g<2>',
                source,
                flags=re.MULTILINE,
            )
    cfg_path.write_text(source)


def _write_laser_task_config(updates: Dict[str, Any]) -> None:
    cfg_path = PROJECT_ROOT / "laserTask" / "config.py"
    source = cfg_path.read_text()

    field_map = {
        "fullscreen": "fullscreen",
        "screen_index": "screen_index",
        "monitor_name": "monitor_name",
        "target_refresh_rate": "target_refresh_rate",
        "key_right": "key_right",
        "key_left": "key_left",
        "input_device": "input_device",
        "rotation_speed": "rotation_speed",
        "circle_radius": "circle_radius",
        "allow_shield_adjustment": "allow_shield_adjustment",
        "loss_factor": "loss_factor",
        "currency_symbol": "currency_symbol",
        "trigger_mode": "trigger_mode",
        "serial_port": "serial_port",
        "serial_baud_rate": "serial_baud_rate",
        "parallel_address": "parallel_address",
        "enable_audio": "enable_audio",
        "tone_freq_standard": "tone_freq_standard",
        "tone_freq_deviant": "tone_freq_deviant",
        "tone_duration": "tone_duration",
        "tone_volume": "tone_volume",
        "tone_isi_frames": "tone_isi_frames",
        "enable_practice": "enable_practice",
        "n_blocks": "n_blocks",
        "min_laser_duration_frames": "min_laser_duration_frames",
        "visits": "visits",
        "sessions": "sessions",
        "orders": "orders",
        "framings": "framings",
        "dialog_fields": "dialog_fields",
        "keyboard_backend": "keyboard_backend",
    }

    # Handle window_size specially
    if "window_size_w" in updates and "window_size_h" in updates:
        new_val = f"({updates['window_size_w']}, {updates['window_size_h']})"
        source = re.sub(
            r'(window_size:\s*\S+\s*=\s*).+?(?=\s*(?:#.*)?$)',
            rf'\g<1>{new_val}',
            source,
            count=1,
            flags=re.MULTILINE,
        )

    for key, value in updates.items():
        field_name = field_map.get(key)
        if field_name is None:
            continue
        if key in ("window_size_w", "window_size_h"):
            continue  # handled above

        if isinstance(value, bool):
            new_val = str(value)
        elif isinstance(value, str) and not value.startswith("["):
            new_val = f'"{value}"'
        elif isinstance(value, list):
            inner = ", ".join(f'"{x}"' for x in value)
            new_val = f"field(default_factory=lambda: [{inner}])"
        else:
            new_val = str(value)

        source = re.sub(
            rf'({field_name}:\s*\S+\s*=\s*).+?(?=\s*(?:#.*)?$)',
            rf'\g<1>{new_val}',
            source,
            count=1,
            flags=re.MULTILINE,
        )
    cfg_path.write_text(source)


def detect_os() -> str:
    """Return 'linux', 'windows', or 'macos'."""
    if sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    return sys.platform


OS_DEFAULTS = {
    "linux": {
        "serial_port": "/dev/ttyUSB0",
        "serial_hint": "Common: /dev/ttyUSB0 or /dev/ttyACM0",
        "parallel_addr": "/dev/parport0",
        "parallel_hint": "Common: /dev/parport0",
    },
    "windows": {
        "serial_port": "COM6",
        "serial_hint": "BrainVision TriggerBox is usually COM6",
        "parallel_addr": "0x0378",
        "parallel_hint": "LPT1 = 0x0378, LPT2 = 0x0278",
    },
    "macos": {
        "serial_port": "/dev/cu.usbserial-*",
        "serial_hint": "Check /dev/cu.* for your USB-serial adapter",
        "parallel_addr": None,
        "parallel_hint": "macOS does not support parallel ports",
    },
}


# ── interactive configuration sections ──────────────────────────────────────

def configure_machine(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Machine Setup")
    info("These settings are specific to your lab computer.")

    current_os = detect_os()
    target_os = prompt(
        "Target operating system",
        current_os,
        choices=["linux", "windows", "macos"],
        hint_text=f"Detected: {current_os} — change if the experiment runs on a different machine",
    )
    cfg["_target_os"] = target_os
    print()

    cfg["monitor_name"] = prompt(
        "Monitor name",
        cfg.get("monitor_name", "testMonitor"),
        hint_text="Must match a PsychoPy monitor calibration entry",
    )
    cfg["fullscreen"] = prompt_yn(
        "Run fullscreen?",
        cfg.get("fullscreen", True),
        hint_text="'No' = windowed mode for testing on a laptop",
    )
    cfg["screen_index"] = prompt_int(
        "Screen index",
        cfg.get("screen_index", 0),
        min_val=0,
        hint_text="0 = primary display; use 1 for the stimulus monitor in multi-screen setups",
    )

    if not cfg["fullscreen"]:
        w = cfg.get("window_size_w", 1512)
        h = cfg.get("window_size_h", 982)
        wh = prompt(
            "Window size (W×H)",
            f"{w}x{h}",
            hint_text="e.g. 800x600 for a small test window",
        )
        try:
            pw, ph = wh.split("x")
            cfg["window_size_w"] = int(pw.strip())
            cfg["window_size_h"] = int(ph.strip())
        except ValueError:
            warn("Invalid format, keeping previous values")

    cfg["target_refresh_rate"] = prompt_int(
        "Target refresh rate (Hz)",
        cfg.get("target_refresh_rate", 60),
        min_val=30,
        hint_text="60 Hz is standard; use 120 or 144 for high-refresh monitors",
    )

    current_os = cfg.get("_target_os", detect_os())
    _kb_os_default = "ptb" if current_os == "windows" else "event"
    cfg["keyboard_backend"] = prompt(
        "Keyboard backend",
        cfg.get("keyboard_backend") or _kb_os_default,
        choices=["event", "ptb", "iohub"],
        hint_text="'event' works everywhere; 'ptb' gives best timing but requires elevated privileges on Linux/macOS",
    )
    return cfg


def configure_input(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Input & Controls")

    dev = prompt(
        "Input device",
        cfg.get("input_device", "keyboard"),
        choices=["keyboard", "response_box"],
        hint_text="'keyboard' for testing; 'response_box' for the real experiment",
    )
    cfg["input_device"] = dev

    if dev == "response_box":
        hint("Enter the key codes your button box actually sends.")
        hint("Common: Current Design FOS response box → '1' / '2'")

    cfg["key_left"] = prompt(
        "Left / CCW key",
        cfg.get("key_left", "f"),
        hint_text="Rotates shield counter-clockwise",
    )
    cfg["key_right"] = prompt(
        "Right / CW key",
        cfg.get("key_right", "j"),
        hint_text="Rotates shield clockwise",
    )
    return cfg


def configure_triggers(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Trigger Setup")

    mode = prompt(
        "Trigger mode",
        cfg.get("trigger_mode", "dummy"),
        choices=["dummy", "serial", "parallel", "lsl"],
        hint_text="'dummy' prints to console — use for testing without hardware",
    )
    cfg["trigger_mode"] = mode

    if mode == "serial":
        osdef = OS_DEFAULTS.get(cfg.get("_target_os", "linux"), OS_DEFAULTS["linux"])
        cfg["serial_port"] = prompt(
            "Serial port",
            cfg.get("serial_port", osdef["serial_port"]),
            hint_text=osdef["serial_hint"],
        )
        cfg["serial_baud_rate"] = prompt_int(
            "Baud rate",
            cfg.get("serial_baud_rate", 115200),
            hint_text="115200 for BrainVision TriggerBox",
        )
    elif mode == "parallel":
        osdef = OS_DEFAULTS.get(cfg.get("_target_os", "linux"), OS_DEFAULTS["linux"])
        if osdef["parallel_addr"] is None:
            warn(f"Parallel ports are not supported on {cfg.get('_target_os', 'linux')}.")
            cfg["trigger_mode"] = "dummy"
            info("Falling back to dummy trigger mode.")
        else:
            cfg["parallel_address"] = prompt(
                "Parallel port address",
                cfg.get("parallel_address", osdef["parallel_addr"]),
                hint_text=osdef["parallel_hint"],
            )
    elif mode == "lsl":
        info("LSL will auto-discover streams at runtime — no extra config needed.")
    else:
        info("Triggers will be printed to the console log only.")

    return cfg


def configure_design(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Experiment Design")

    cfg["n_blocks"] = prompt_int(
        "Blocks per session",
        cfg.get("n_blocks", 4),
        min_val=1,
        max_val=20,
        hint_text="How many main blocks the participant plays (default: 4)",
    )
    cfg["enable_practice"] = prompt_yn(
        "Include practice block?",
        cfg.get("enable_practice", True),
        hint_text="Shown before the main blocks; good for first-time participants",
    )
    return cfg


def configure_dialog(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Startup Dialog Options")

    # ── which fields appear (interactive multiselect) ──
    available_fields = ["participant", "visit", "session", "order", "framing"]
    current_fields = cfg.get("dialog_fields", ["participant", "visit", "session", "order", "framing"])

    cfg["dialog_fields"], _ = prompt_multiselect(
        "Which fields should appear in the session dialog?",
        available_fields,
        defaults=current_fields,
        hint_text="space=toggle  ↑↓/jk=navigate  enter=confirm",
    )

    # Always force-include participant (required for data files)
    if "participant" not in cfg["dialog_fields"]:
        cfg["dialog_fields"] = ["participant"] + cfg["dialog_fields"]
        info("'participant' was force-included (required for data-file naming).")

    # ── dropdown options for known fields ──
    visits = cfg.get("visits", ["1", "2"])
    sessions = cfg.get("sessions", ["1", "2"])
    orders = cfg.get("orders", ["1", "2"])
    framings = cfg.get("framings", ["loss", "win"])

    cfg["visits"] = prompt_list(
        "Visit options",
        visits,
        hint_text="Comma-separated values shown in the visit dropdown (e.g. 1,2,3)",
    )
    cfg["sessions"] = prompt_list(
        "Session options",
        sessions,
        hint_text="Comma-separated values shown in the session dropdown (e.g. 1,2)",
    )
    cfg["orders"] = prompt_list(
        "Order options",
        orders,
        hint_text="Comma-separated; 1,2,3,4 gives full counterbalancing",
    )
    cfg["framings"] = prompt_list(
        "Framing options",
        framings,
        hint_text="Comma-separated; e.g. 'loss,win' or just 'loss' to fix the framing",
    )

    visible = [f for f in cfg["dialog_fields"] if f in ("visit", "session", "order", "framing")]
    if visible:
        info(f"  → Experimenter will choose from: {' × '.join(visible)} combinations")
    return cfg


def configure_shield_reward(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Shield & Reward")

    cfg["allow_shield_adjustment"] = prompt_yn(
        "Allow participant to resize shield?",
        cfg.get("allow_shield_adjustment", False),
        hint_text="If yes, they can press grow/shrink keys during the task",
    )

    cfg["rotation_speed"] = prompt_float(
        "Shield rotation speed",
        cfg.get("rotation_speed", 1.0),
        hint_text="Degrees per frame — how fast the shield moves when a key is held (default: 1.0)",
    )
    cfg["circle_radius"] = prompt_float(
        "Circle radius",
        cfg.get("circle_radius", 3.0),
        hint_text="PsychoPy height units — size of the game circle (default: 3.0)",
    )
    cfg["loss_factor"] = prompt_float(
        "Loss factor",
        cfg.get("loss_factor", 0.003),
        hint_text="Reward scaling multiplier applied to miss penalties (default: 0.003)",
    )
    cfg["currency_symbol"] = prompt(
        "Currency symbol",
        cfg.get("currency_symbol", "£"),
        hint_text="Displayed to the participant (default: £)",
    )

    cfg["min_laser_duration_frames"] = prompt_int(
        "Min laser duration (frames)",
        cfg.get("min_laser_duration_frames", 6),
        min_val=1,
        max_val=60,
        hint_text="Observations shorter than this are merged into the previous one (default: 6 frames = 100 ms at 60 Hz)",
    )
    return cfg


def configure_audio(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Auditory MMN  —  Background Tones")

    cfg["enable_audio"] = prompt_yn(
        "Enable background tones?",
        cfg.get("enable_audio", True),
        hint_text="Plays standard/deviant tones during the main blocks (Mismatch Negativity paradigm)",
    )

    if not cfg["enable_audio"]:
        info("Audio disabled — no tones will play.")
        return cfg

    cfg["tone_freq_standard"] = prompt_float(
        "Standard tone frequency (Hz)",
        cfg.get("tone_freq_standard", 440.0),
        hint_text="Pitch of the frequent tone (default: 440 Hz = A4)",
    )
    cfg["tone_freq_deviant"] = prompt_float(
        "Deviant tone frequency (Hz)",
        cfg.get("tone_freq_deviant", 528.0),
        hint_text="Pitch of the rare tone (default: 528 Hz ≈ C5)",
    )
    duration_ms = int(cfg.get("tone_duration", 0.07) * 1000)
    cfg["tone_duration"] = (
        prompt_int(
            "Tone duration (ms)",
            duration_ms,
            min_val=10,
            max_val=500,
            hint_text="How long each tone plays (default: 70 ms)",
        )
        / 1000.0
    )
    cfg["tone_isi_frames"] = prompt_int(
        "Inter-stimulus interval (frames)",
        cfg.get("tone_isi_frames", 26),
        min_val=1,
        hint_text=f"Gap between tones in frames (default: 26 frames = ~{26/60*1000:.0f} ms at 60 Hz)",
    )
    fps = cfg.get("target_refresh_rate", 60)
    info(f"  → Effective ISI: ~{cfg['tone_isi_frames'] / fps * 1000:.0f} ms at {fps} Hz")

    cfg["tone_volume"] = prompt_float(
        "Tone volume",
        cfg.get("tone_volume", 1.0),
        hint_text="0.0 = silent, 1.0 = full volume (default: 1.0)",
    )
    return cfg


def configure_stimgen(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Sequence Generation Parameters")
    info("Generation always produces all session types. Configure each below.")
    info("Press Enter at any prompt to keep the current value.")

    stimgen = _read_stimgen_config()

    # ── practice ──
    ps = stimgen.get("PRACTICE_SESSION", {})
    print()
    info(_c(C["bold"], "Practice session"))
    stimgen["_practice_block_dur"] = prompt_int(
        "  Block duration (min)",
        ps.get("blockDurationMin", 1), min_val=1,
        hint_text="1 minute is standard for a short practice",
    )
    stimgen["_practice_n_blocks"] = prompt_int(
        "  Number of blocks",
        ps.get("nBlocks", 4), min_val=1, max_val=20,
        hint_text="Usually 4 blocks covering all condition types",
    )

    # ── online training ──
    ot = stimgen.get("ONLINE_TRAINING_SESSION", {})
    print()
    info(_c(C["bold"], "Online training session"))
    stimgen["_online_block_dur"] = prompt_float(
        "  Block duration (min)",
        ot.get("blockDurationMin", 0.5),
        hint_text="Shorter blocks for online training (default: 0.5 min = 30 s)",
    )
    stimgen["_online_n_blocks"] = prompt_int(
        "  Number of blocks",
        ot.get("nBlocks", 4), min_val=1, max_val=20,
        hint_text="Usually a short subset of condition types",
    )

    # ── main / baseline ──
    ms = stimgen.get("MAIN_SESSION", {})
    print()
    info(_c(C["bold"], "Main & baseline sessions"))
    stimgen["_main_block_dur"] = prompt_int(
        "  Block duration (min)",
        ms.get("blockDurationMin", 3), min_val=1,
        hint_text="3 minutes is standard for MEG/EEG blocks",
    )
    stimgen["_main_n_blocks"] = prompt_int(
        "  Number of blocks (main)",
        ms.get("nBlocks", 12), min_val=1, max_val=30,
        hint_text="12 blocks = 4 condition types × 3 repetitions",
    )

    # ── common ──
    print()
    info(_c(C["bold"], "Common parameters (all session types)"))
    stimgen["NOISE_STD_LOW"] = prompt_int(
        "  Observation noise — low (°)",
        stimgen.get("NOISE_STD_LOW", 10), min_val=1,
        hint_text="Standard deviation in low-noise blocks (default: 10°)",
    )
    stimgen["NOISE_STD_HIGH"] = prompt_int(
        "  Observation noise — high (°)",
        stimgen.get("NOISE_STD_HIGH", 20), min_val=1,
        hint_text="Standard deviation in high-noise blocks (default: 20°)",
    )
    stimgen["JUMP_DURATION_MEAN_SEC"] = prompt_float(
        "  Mean jump duration (s)",
        stimgen.get("JUMP_DURATION_MEAN_SEC", 0.3),
        hint_text="How long the true mean stays in one position (default: 0.3 s)",
    )

    cfg["_stimgen_updates"] = stimgen
    return cfg


# ── summary table ───────────────────────────────────────────────────────────

def _kv(label: str, value: Any, suffix: str = "") -> str:
    s = str(value)
    return f"  {_c(C['dim'], label + ':').ljust(28)} {_c(C['bold'], s)}{suffix}"


def show_summary(cfg: Dict[str, Any]) -> None:
    section("Configuration Summary")

    width = 59
    print(_c(C["cyan"], f"  ┌{'─' * (width - 4)}┐"))

    fullscr = "fullscreen" if cfg.get("fullscreen") else f"{cfg.get('window_size_w', '?')}×{cfg.get('window_size_h', '?')}"
    items = [
        ("Target OS", cfg.get("_target_os", detect_os())),
        ("Keyboard backend", cfg.get("keyboard_backend", "?")),
        ("Monitor", f"{cfg.get('monitor_name', '?')} ({fullscr})"),
        ("Screen index", cfg.get("screen_index", "?")),
        ("Refresh rate", f"{cfg.get('target_refresh_rate', '?')} Hz"),
        ("Input", f"{cfg.get('input_device', '?')}  ({cfg.get('key_left', '?')} / {cfg.get('key_right', '?')})"),
        ("Triggers", cfg.get("trigger_mode", "?")),
    ]
    if cfg.get("trigger_mode") == "serial":
        items.append(("  Serial port", cfg.get("serial_port", "?")))
        items.append(("  Baud rate", cfg.get("serial_baud_rate", "?")))
    elif cfg.get("trigger_mode") == "parallel":
        items.append(("  Parallel addr", cfg.get("parallel_address", "?")))

    items += [
        ("Blocks", f"{cfg.get('n_blocks', '?')} main" + (" + 1 practice" if cfg.get("enable_practice") else "")),
        ("Shield", f"{'adjustable' if cfg.get('allow_shield_adjustment') else 'fixed'}  ({cfg.get('rotation_speed', '?')}°/frame, r={cfg.get('circle_radius', '?')})"),
        ("Loss factor", f"{cfg.get('loss_factor', '?')}  ({cfg.get('currency_symbol', '?')})"),
        ("Min laser dur", f"{cfg.get('min_laser_duration_frames', '?')} frames"),
    ]

    if cfg.get("enable_audio"):
        items += [
            ("Tones", f"{cfg.get('tone_freq_standard', '?')} / {cfg.get('tone_freq_deviant', '?')} Hz"),
            ("Tone dur / ISI", f"{cfg.get('tone_duration', '?')*1000:.0f} ms / {cfg.get('tone_isi_frames', '?')} frames"),
            ("Tone volume", cfg.get("tone_volume", "?")),
        ]
    else:
        items.append(("Tones", _c(C["dim"], "disabled")))

    items += [
        ("Seq version", f"main={SEQUENCE_VERSION}, practice={PRACTICE_SEQUENCE_VERSION}"),
        ("Visits", f"{', '.join(cfg.get('visits', ['?']))}"),
        ("Sessions", f"{', '.join(cfg.get('sessions', ['?']))}"),
        ("Orders", f"{', '.join(cfg.get('orders', ['?']))}"),
        ("Framings", f"{', '.join(cfg.get('framings', ['?']))}"),
    ]

    for label, value in items:
        line = _kv(label, value)
        print(_c(C["cyan"], "  │") + line.ljust(width - 2) + _c(C["cyan"], "│"))

    print(_c(C["cyan"], f"  └{'─' * (width - 4)}┘"))
    print()


# ── sequence generation ─────────────────────────────────────────────────────

def run_sequence_generation(cfg: Dict[str, Any]) -> bool:
    section("Generating Sequences")

    _save_stimgen_from_cfg(cfg)

    # Laser sequences
    info("Generating laser stimulus sequences …")
    laser_dir = PROJECT_ROOT / "stimgen" / "laser"
    result = subprocess.run(
        [sys.executable, "coin_script_sequence_generation.py"],
        cwd=str(laser_dir),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        fail("Laser sequence generation failed!")
        print(_c(C["red"], result.stderr[-500:]))
        return False
    success("Laser sequences written")
    for line in result.stdout.strip().split("\n")[-3:]:
        if line.strip():
            info(line.strip())

    # MMN sequences
    info("Generating MMN tone sequences …")
    mmn_out = str(PROJECT_ROOT / "sequences" / "mmn")
    result = subprocess.run(
        [
            sys.executable, "-c",
            f"from stimgen.mmn.generate_all_peduks_sessions import generate_all_peduks_sessions; "
            f"generate_all_peduks_sessions('{mmn_out}')",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        fail("MMN sequence generation failed!")
        print(_c(C["red"], result.stderr[-500:]))
        return False
    success("MMN tone sequences written to sequences/mmn/")
    return True


# ── report mode ──────────────────────────────────────────────────────────────

def print_report() -> None:
    header("Current Configuration Report")

    cfg = _read_laser_task_config()

    section("config_shared.py")
    print(_kv("SEQUENCE_VERSION", SEQUENCE_VERSION))
    print(_kv("PRACTICE_SEQUENCE_VERSION", PRACTICE_SEQUENCE_VERSION))
    print(_kv("SEQUENCE_ROOT", SEQUENCE_ROOT))

    show_summary(cfg)

    section("stimgen/laser/config.py")
    stimgen = _read_stimgen_config()
    for key in [
        "SAMPLE_RATE", "NOISE_STD_LOW", "NOISE_STD_HIGH",
        "JUMP_DURATION_MEAN_SEC", "JUMP_DURATION_MIN_SEC", "JUMP_DURATION_MAX_SEC",
    ]:
        if key in stimgen:
            print(_kv(key, stimgen[key]))
    if "MAIN_SESSION" in stimgen:
        print(_kv("MAIN_SESSION.nBlocks", stimgen["MAIN_SESSION"]["nBlocks"]))
        print(_kv("MAIN_SESSION.blockDurationMin", f"{stimgen['MAIN_SESSION']['blockDurationMin']} min"))
    if "PRACTICE_SESSION" in stimgen:
        print(_kv("PRACTICE_SESSION.blockDurationMin", f"{stimgen['PRACTICE_SESSION']['blockDurationMin']} min"))

    section("Generated Sequences")
    seq_dir = PROJECT_ROOT / "sequences"
    if seq_dir.exists():
        csv_count = len(list(seq_dir.glob("*.csv")))
        mmn_count = len(list((seq_dir / "mmn").glob("*.csv"))) if (seq_dir / "mmn").exists() else 0
        order_count = len([d for d in seq_dir.iterdir() if d.is_dir() and d.name.startswith("coin_")])
        print(_kv("Block CSVs", csv_count))
        print(_kv("MMN tone CSVs", mmn_count))
        print(_kv("Order directories", order_count))
    else:
        warn("sequences/ directory does not exist — run setup to generate")
    print()


# ── section menu ─────────────────────────────────────────────────────────────

SECTION_REGISTRY: List[Tuple[str, str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = [
    ("1", "Machine setup (monitor, fullscreen, refresh rate)", configure_machine),
    ("2", "Input & controls (keyboard vs. response box, keys)", configure_input),
    ("3", "Trigger mode & hardware ports", configure_triggers),
    ("4", "Experiment design (blocks, practice)", configure_design),
    ("5", "Shield mechanics & reward (size, speed, loss factor)", configure_shield_reward),
    ("6", "Auditory MMN (tone frequencies, duration, ISI)", configure_audio),
    ("7", "Sequence generation (noise levels, volatility, durations)", configure_stimgen),
    ("8", "Startup dialog (which fields, dropdown options, framing)", configure_dialog),
]

SECTION_MAP: Dict[str, Tuple[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = {
    slug: (desc, fn) for slug, desc, fn in SECTION_REGISTRY
}


def run_section_menu(cfg: Dict[str, Any]) -> None:
    """Interactive menu — multi-select sections with space, arrows to navigate."""
    dirty = False

    ALL_SECTIONS = [(slug, desc, fn) for slug, desc, fn in SECTION_REGISTRY]
    slug_to_fn = {slug: fn for slug, _, fn in ALL_SECTIONS}
    all_options = [f"{slug}. {desc}" for slug, desc, _ in ALL_SECTIONS]
    all_slugs = [slug for slug, _, _ in ALL_SECTIONS]

    while True:
        dirty_warn = _c(C["yellow"], "  ← unsaved changes in memory") if dirty else ""

        selected_labels, action = prompt_multiselect(
            "Select sections to configure",
            all_options,
            defaults=[],
            header_text="CoIn Laser Task — Setup",
            hint_text=dirty_warn or "space=toggle  ↑↓/jk=navigate  enter=run selected",
            action_keys={
                "r": "run experiment",
                "g": "generate sequences",
                "s": "show config",
                "q": "quit & save",
            },
        )

        # ── action keys ──
        if action == "q":
            break
        elif action == "s":
            show_summary(cfg)
            input(_c(C["dim"], "  Press Enter to continue …"))
            continue
        elif action == "r":
            if dirty:
                warn("Unsaved config changes — run anyway?")
                if not prompt_yn("Proceed without saving?", True):
                    continue
            print()
            info("Launching experiment …")
            print()
            subprocess.run([sys.executable, str(PROJECT_ROOT / "main.py")])
            return
        elif action == "g":
            show_summary(cfg)
            if dirty:
                warn("You have unsaved config changes.")
                if prompt_yn("Save before generating?", True):
                    _write_laser_task_config(cfg)
                    if _save_stimgen_from_cfg(cfg.copy()):
                        dirty = False
            if prompt_yn("Generate sequences now?", True):
                if run_sequence_generation(cfg.copy()):
                    print()
                    if prompt_yn("Start the experiment?", True):
                        subprocess.run([sys.executable, str(PROJECT_ROOT / "main.py")])
                        return
            continue

        # ── run selected sections ──
        if not selected_labels:
            continue

        selected_slugs = []
        for label in selected_labels:
            slug = label.split(".")[0]
            selected_slugs.append(slug)

        info(f"Running {len(selected_slugs)} section(s): {', '.join(selected_slugs)}")
        for slug in selected_slugs:
            fn = slug_to_fn[slug]
            cfg = fn(cfg)
            dirty = True

        show_summary(cfg)
        if prompt_yn("Save all changes?", True):
            _write_laser_task_config(cfg)
            _save_stimgen_from_cfg(cfg.copy())
            dirty = False
            success("Configuration saved.")
        else:
            info("Changes held in memory — save later with 'q'.")
        input(_c(C["dim"], "  Press Enter to continue …"))

    if dirty:
        print()
        if prompt_yn("Save unsaved changes before exiting?", True):
            _write_laser_task_config(cfg)
            success("Configuration saved.")

    print()
    info("Ready.  Run the experiment with:")
    print(_c(C["green"], f"\n    cd {PROJECT_ROOT}"))
    print(_c(C["green"], "    python main.py\n"))


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    if "--report" in sys.argv:
        print_report()
        return

    if "--generate" in sys.argv:
        cfg = _read_laser_task_config()
        if run_sequence_generation(cfg):
            print()
            success("All sequences regenerated.")
        else:
            print()
            fail("Sequence generation had errors — check output above.")
        return

    # ── interactive ──
    cfg = _read_laser_task_config()

    if "--full" in sys.argv:
        # Straight into the full wizard
        clear()
        header("CoIn Laser Task — Full Setup Wizard")
        cfg = configure_machine(cfg)
        cfg = configure_input(cfg)
        cfg = configure_triggers(cfg)
        cfg = configure_design(cfg)
        cfg = configure_shield_reward(cfg)
        cfg = configure_audio(cfg)
        cfg = configure_dialog(cfg)
        cfg = configure_stimgen(cfg)
        show_summary(cfg)
        if prompt_yn("Save configuration and proceed?", True):
            _write_laser_task_config(cfg)
            _save_stimgen_from_cfg(cfg.copy())
            success("Configuration saved.")
            if prompt_yn("Generate sequences now?", True):
                if run_sequence_generation(cfg.copy()):
                    print()
                    header("Setup Complete")
                    print()
                    info("Run the experiment with:")
                    print(_c(C["green"], f"    cd {PROJECT_ROOT}"))
                    print(_c(C["green"], "    python main.py"))
            else:
                print()
                info("Run the experiment with:")
                print(_c(C["green"], f"    cd {PROJECT_ROOT}"))
                print(_c(C["green"], "    python main.py"))
    else:
        run_section_menu(cfg)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print()
        warn("Setup cancelled.")
        sys.exit(0)
    except EOFError:
        print()
        print()
        warn("Setup cancelled (EOF).")
        sys.exit(0)
