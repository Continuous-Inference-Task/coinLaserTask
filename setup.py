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
import textwrap
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
        hint(hint_text)
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


# ── config readers / writers ────────────────────────────────────────────────

def _read_py_config(path: Path) -> Dict[str, Any]:
    namespace: Dict[str, Any] = {}
    if not path.exists():
        return namespace
    source = path.read_text()
    for match in re.finditer(
        r'^(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<value>.+?)(?:\s*#.*)?$',
        source,
        re.MULTILINE,
    ):
        name = match.group("name")
        value_str = match.group("value").strip()
        if name.startswith("_"):
            continue
        try:
            namespace[name] = eval(value_str, {"__builtins__": {}}, {})
        except Exception:
            pass
    return namespace


def _read_laser_task_config() -> Dict[str, Any]:
    cfg_path = PROJECT_ROOT / "laserTask" / "config.py"
    source = cfg_path.read_text()
    result: Dict[str, Any] = {}

    patterns = {
        "window_size_w": (r'window_size:\s*Tuple\[int,\s*int\]\s*=\s*\((\d+),\s*(\d+)\)', 1),
        "window_size_h": (r'window_size:\s*Tuple\[int,\s*int\]\s*=\s*\((\d+),\s*(\d+)\)', 2),
        "fullscreen": (r'fullscreen:\s*bool\s*=\s*(True|False)', 1),
        "screen_index": (r'screen_index:\s*int\s*=\s*(\d+)', 1),
        "monitor_name": (r'monitor_name:\s*str\s*=\s*"([^"]*)"', 1),
        "target_refresh_rate": (r'target_refresh_rate:\s*int\s*=\s*(\d+)', 1),
        "key_right": (r'key_right:\s*str\s*=\s*"([^"]*)"', 1),
        "key_left": (r'key_left:\s*str\s*=\s*"([^"]*)"', 1),
        "input_device": (r'input_device:\s*str\s*=\s*"([^"]*)"', 1),
        "rotation_speed": (r'rotation_speed:\s*float\s*=\s*([\d.]+)', 1),
        "circle_radius": (r'circle_radius:\s*float\s*=\s*([\d.]+)', 1),
        "allow_shield_adjustment": (r'allow_shield_adjustment:\s*bool\s*=\s*(True|False)', 1),
        "loss_factor": (r'loss_factor:\s*float\s*=\s*([\d.]+)', 1),
        "currency_symbol": (r'currency_symbol:\s*str\s*=\s*"([^"]*)"', 1),
        "trigger_mode": (r'trigger_mode:\s*str\s*=\s*"([^"]*)"', 1),
        "serial_port": (r'serial_port:\s*str\s*=\s*"([^"]*)"', 1),
        "serial_baud_rate": (r'serial_baud_rate:\s*int\s*=\s*(\d+)', 1),
        "parallel_address": (r'parallel_address:\s*int\s*=\s*(0x[0-9A-Fa-f]+)', 1),
        "enable_audio": (r'enable_audio:\s*bool\s*=\s*(True|False)', 1),
        "tone_freq_standard": (r'tone_freq_standard:\s*float\s*=\s*([\d.]+)', 1),
        "tone_freq_deviant": (r'tone_freq_deviant:\s*float\s*=\s*([\d.]+)', 1),
        "tone_duration": (r'tone_duration:\s*float\s*=\s*([\d.]+)', 1),
        "tone_volume": (r'tone_volume:\s*float\s*=\s*([\d.]+)', 1),
        "tone_isi_frames": (r'tone_isi_frames:\s*int\s*=\s*(\d+)', 1),
        "enable_practice": (r'enable_practice:\s*bool\s*=\s*(True|False)', 1),
        "n_blocks": (r'n_blocks:\s*int\s*=\s*(\d+)', 1),
        "min_laser_duration_frames": (r'min_laser_duration_frames:\s*int\s*=\s*(\d+)', 1),
    }

    for key, (pat, group) in patterns.items():
        m = re.search(pat, source)
        if m:
            val = m.group(group)
            if val in ("True", "False"):
                result[key] = val == "True"
            elif val.startswith("0x"):
                result[key] = int(val, 16)
            elif "." in val:
                try:
                    result[key] = float(val)
                except ValueError:
                    result[key] = val
            else:
                try:
                    result[key] = int(val)
                except ValueError:
                    result[key] = val

    for list_key, pat in [
        ("visits", r'visits:\s*list\s*=\s*(?:field\(default_factory=lambda:\s*)?\[(.*?)\](?:\))?'),
        ("sessions", r'sessions:\s*list\s*=\s*(?:field\(default_factory=lambda:\s*)?\[(.*?)\](?:\))?'),
        ("orders", r'orders:\s*list\s*=\s*(?:field\(default_factory=lambda:\s*)?\[(.*?)\](?:\))?'),
    ]:
        m = re.search(pat, source)
        if m:
            result[list_key] = [x.strip().strip('"').strip("'") for x in m.group(1).split(",")]

    return result


def _read_stimgen_config() -> Dict[str, Any]:
    return _read_py_config(PROJECT_ROOT / "stimgen" / "laser" / "config.py")


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
    }

    # Handle window_size specially
    if "window_size_w" in updates and "window_size_h" in updates:
        new_val = f"({updates['window_size_w']}, {updates['window_size_h']})"
        source = re.sub(
            r'(window_size:\s*\S+\s*=\s*).+?(?=\s*(?:#.*)?$)',
            rf'\1{new_val}',
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
            new_val = "[" + ", ".join(f'"{x}"' for x in value) + "]"
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


# ── interactive configuration sections ──────────────────────────────────────

def configure_machine(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Machine Setup")
    info("These settings are specific to your lab computer.")

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
        cfg["serial_port"] = prompt(
            "Serial port",
            cfg.get("serial_port", "COM6"),
            hint_text="BrainVision TriggerBox is usually COM6 on Windows, /dev/ttyUSB0 on Linux",
        )
        cfg["serial_baud_rate"] = prompt_int(
            "Baud rate",
            cfg.get("serial_baud_rate", 115200),
            hint_text="115200 for BrainVision TriggerBox",
        )
    elif mode == "parallel":
        cfg["parallel_address"] = prompt(
            "Parallel port address",
            cfg.get("parallel_address", "0x0378"),
            hint_text="LPT1 = 0x0378, LPT2 = 0x0278 (common on older setups)",
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

    visits = cfg.get("visits", ["1", "2"])
    sessions = cfg.get("sessions", ["1", "2"])
    orders = cfg.get("orders", ["1", "2"])

    cfg["visits"] = prompt_list(
        "Visit numbers",
        visits,
        hint_text="Comma-separated list shown in the pre-experiment dropdown",
    )
    cfg["sessions"] = prompt_list(
        "Session numbers",
        sessions,
        hint_text="Comma-separated; usually 1–2 for a two-session study",
    )
    cfg["orders"] = prompt_list(
        "Order numbers",
        orders,
        hint_text="Comma-separated; 1–4 gives full counterbalancing (2 stable-first, 2 volatile-first)",
    )

    n_visits = len(cfg["visits"])
    n_sessions = len(cfg["sessions"])
    n_orders = len(cfg["orders"])
    info(
        f"Design matrix: {n_visits} visits × {n_sessions} sessions "
        f"× {n_orders} orders = {n_visits * n_sessions * n_orders} possible combinations"
    )
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
    info("These control noise levels, volatility, and block durations.")

    stimgen = _read_stimgen_config()

    stimgen["NOISE_STD_LOW"] = prompt_int(
        "Observation noise — low (degrees)",
        stimgen.get("NOISE_STD_LOW", 10),
        min_val=1,
        hint_text="Standard deviation of laser observations around true mean in low-noise blocks (default: 10°)",
    )
    stimgen["NOISE_STD_HIGH"] = prompt_int(
        "Observation noise — high (degrees)",
        stimgen.get("NOISE_STD_HIGH", 20),
        min_val=1,
        hint_text="Standard deviation in high-noise blocks (default: 20°)",
    )
    stimgen["JUMP_DURATION_MEAN_SEC"] = prompt_float(
        "Mean jump duration (seconds)",
        stimgen.get("JUMP_DURATION_MEAN_SEC", 0.3),
        hint_text="On average, how long the true mean stays in one position before jumping (default: 0.3 s)",
    )

    ms = stimgen.get("MAIN_SESSION", {})
    stimgen["_main_block_dur"] = prompt_int(
        "Main block duration (minutes)",
        ms.get("blockDurationMin", 3),
        min_val=1,
        hint_text="How long each main block lasts (default: 3 min)",
    )
    ps = stimgen.get("PRACTICE_SESSION", {})
    stimgen["_practice_block_dur"] = prompt_int(
        "Practice block duration (minutes)",
        ps.get("blockDurationMin", 1),
        min_val=1,
        hint_text="How long the practice block lasts (default: 1 min)",
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
        ("Monitor", f"{cfg.get('monitor_name', '?')} ({fullscr})"),
        ("Refresh rate", f"{cfg.get('target_refresh_rate', '?')} Hz"),
        ("Input", f"{cfg.get('input_device', '?')}  ({cfg.get('key_left', '?')} / {cfg.get('key_right', '?')})"),
        ("Triggers", cfg.get("trigger_mode", "?")),
    ]
    if cfg.get("trigger_mode") == "serial":
        items.append(("  Serial port", cfg.get("serial_port", "?")))
    elif cfg.get("trigger_mode") == "parallel":
        items.append(("  Parallel addr", cfg.get("parallel_address", "?")))

    items += [
        ("Blocks", f"{cfg.get('n_blocks', '?')} main" + (" + 1 practice" if cfg.get("enable_practice") else "")),
        ("Shield", f"{'adjustable' if cfg.get('allow_shield_adjustment') else 'fixed'}  ({cfg.get('rotation_speed', '?')}°/frame, r={cfg.get('circle_radius', '?')})"),
        ("Loss factor", cfg.get("loss_factor", "?")),
        ("Min laser dur", f"{cfg.get('min_laser_duration_frames', '?')} frames"),
    ]

    if cfg.get("enable_audio"):
        items += [
            ("Tones", f"{cfg.get('tone_freq_standard', '?')} / {cfg.get('tone_freq_deviant', '?')} Hz"),
            ("Tone dur / ISI", f"{cfg.get('tone_duration', '?')*1000:.0f} ms / {cfg.get('tone_isi_frames', '?')} frames"),
        ]
    else:
        items.append(("Tones", _c(C["dim"], "disabled")))

    items += [
        ("Seq version", f"main={SEQUENCE_VERSION}, practice={PRACTICE_SEQUENCE_VERSION}"),
        ("Orders", f"{', '.join(cfg.get('orders', ['?']))}"),
    ]

    for label, value in items:
        line = _kv(label, value)
        print(_c(C["cyan"], "  │") + line.ljust(width - 2) + _c(C["cyan"], "│"))

    print(_c(C["cyan"], f"  └{'─' * (width - 4)}┘"))
    print()


# ── sequence generation ─────────────────────────────────────────────────────

def run_sequence_generation(cfg: Dict[str, Any]) -> bool:
    section("Generating Sequences")

    stimgen_updates = cfg.pop("_stimgen_updates", None)
    if stimgen_updates:
        # Flatten the special keys into the stimgen config format
        ms = _read_stimgen_config()
        ms_dict = ms.get("MAIN_SESSION", {})
        ps_dict = ms.get("PRACTICE_SESSION", {})

        flat: Dict[str, Any] = {}
        for k, v in stimgen_updates.items():
            if k == "_main_block_dur":
                ms_dict["blockDurationMin"] = v
            elif k == "_practice_block_dur":
                ps_dict["blockDurationMin"] = v
            elif not k.startswith("_"):
                flat[k] = v

        if ms_dict:
            flat["MAIN_SESSION"] = ms_dict
        if ps_dict:
            flat["PRACTICE_SESSION"] = ps_dict
        _write_stimgen_config(flat)

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
    mmn_dir = PROJECT_ROOT / "stimgen" / "mmn"
    mmn_out = str(PROJECT_ROOT / "sequences" / "mmn")
    result = subprocess.run(
        [
            sys.executable, "-c",
            f"from generate_all_peduks_sessions import generate_all_peduks_sessions; "
            f"generate_all_peduks_sessions('{mmn_out}')",
        ],
        cwd=str(mmn_dir),
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
    ("4", "Experiment design (blocks, visits, sessions, orders)", configure_design),
    ("5", "Shield mechanics & reward (size, speed, loss factor)", configure_shield_reward),
    ("6", "Auditory MMN (tone frequencies, duration, ISI)", configure_audio),
    ("7", "Sequence generation (noise levels, volatility, durations)", configure_stimgen),
]

SECTION_MAP: Dict[str, Tuple[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = {
    slug: (desc, fn) for slug, desc, fn in SECTION_REGISTRY
}


def run_section_menu(cfg: Dict[str, Any]) -> None:
    """Interactive menu: pick sections to configure, or run actions."""
    dirty = False

    while True:
        clear()
        header("CoIn Laser Task — Setup")

        print("  Sections to configure:\n")
        for slug, desc, _ in SECTION_REGISTRY:
            print(f"    {_c(C['green'], slug)})  {desc}")

        print()
        print(f"    {_c(C['green'], 'a')})  Configure everything (all sections)")
        print(f"  {_c(C['cyan'], 's')})  Show current configuration")
        print(f"  {_c(C['cyan'], 'g')})  Generate sequences")
        if dirty:
            print(f"  {_c(C['yellow'], '  (unsaved changes in memory)')}")
        print(f"  {_c(C['dim'], 'q')})  Quit & save")

        print()
        choice = input(f"  {_c(C['bold'], '>')} ").strip().lower()

        if choice == "q":
            break
        elif choice == "s":
            show_summary(cfg)
        elif choice == "a":
            cfg = configure_machine(cfg)
            cfg = configure_input(cfg)
            cfg = configure_triggers(cfg)
            cfg = configure_design(cfg)
            cfg = configure_shield_reward(cfg)
            cfg = configure_audio(cfg)
            cfg = configure_stimgen(cfg)
            dirty = True
            show_summary(cfg)
            if prompt_yn("Save all changes?", True):
                _write_laser_task_config(cfg)
                dirty = False
                success("Configuration saved.")
                if prompt_yn("Generate sequences now?", True):
                    if run_sequence_generation(cfg.copy()):
                        dirty = False
            else:
                info("Changes held in memory — save later with 'q'.")
        elif choice == "g":
            show_summary(cfg)
            if dirty:
                warn("You have unsaved config changes.")
                if prompt_yn("Save before generating?", True):
                    _write_laser_task_config(cfg)
                    dirty = False
                    success("Saved.")
            if prompt_yn("Generate sequences with current settings?", True):
                run_sequence_generation(cfg.copy())
        elif choice in SECTION_MAP:
            desc, fn = SECTION_MAP[choice]
            cfg = fn(cfg)
            dirty = True
            show_summary(cfg)
            if prompt_yn("Save this section?", True):
                _write_laser_task_config(cfg)
                dirty = False
                success(f"Section {choice} saved.")
            else:
                info("Change held in memory.")
        else:
            warn(f"Unknown option: '{choice}'")

        if choice != "q":
            print()
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
        cfg = configure_stimgen(cfg)
        show_summary(cfg)
        if prompt_yn("Save configuration and proceed?", True):
            _write_laser_task_config(cfg)
            success("Configuration saved.")
            if prompt_yn("Generate sequences now?", True):
                if run_sequence_generation(cfg.copy()):
                    print()
                    header("Setup Complete")
                    info("Run the experiment:")
                    print(_c(C["green"], f"\n    cd {PROJECT_ROOT}"))
                    print(_c(C["green"], "    python main.py\n"))
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
