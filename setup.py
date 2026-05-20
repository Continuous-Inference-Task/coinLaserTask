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
    """Ask the user for input. Shows default and optional hint below."""
    if choices:
        for i, choice in enumerate(choices, 1):
            marker = _c(C["green"], "→") if choice == default else " "
            print(f"     {marker} {i}. {choice}")
        print()

    while True:
        default_display = _c(C["dim"], f" ({default})") if default else ""
        print(f"  {_c(C['bold'], text)}{default_display}")
        if hint_text:
            print(_c(C["dim"], f"     {hint_text}"))
        raw = input(_c(C["magenta"], "  ❯ ")).strip()
        val = raw if raw else default

        if choices:
            if val in choices:
                return val
            if val.isdigit() and 1 <= int(val) <= len(choices):
                return choices[int(val) - 1]
            warn(f"Invalid option. Please enter a number (1-{len(choices)}) or type the choice exactly.")
            print()
            continue

        return val


def prompt_yn(text: str, default: bool = True, *, hint_text: str = "") -> bool:
    hint_label = "Y/n" if default else "y/N"
    raw = prompt(text, hint_label, hint_text=hint_text).strip().lower()
    if not raw or raw == hint_label.lower():
        return default
    if raw in ("y", "yes"):
        return True
    if raw in ("n", "no"):
        return False
    return default


def prompt_live(
    text: str,
    default: str = "",
    *,
    hint_text: str = "",
    live_formatter = None,
) -> str:
    """Ask the user for input. Shows default, optional hint below, and live previews if possible."""
    use_live = sys.stdin.isatty()
    
    if use_live:
        try:
            if sys.platform == "win32":
                import msvcrt
                def get_char():
                    ch = msvcrt.getch()
                    if ch in (b'\x00', b'\xe0'):
                        msvcrt.getch()
                        return ""
                    return ch.decode("utf-8", errors="ignore")
            else:
                import termios
                import tty
                def get_char():
                    fd = sys.stdin.fileno()
                    old = termios.tcgetattr(fd)
                    try:
                        tty.setraw(fd)
                        ch = sys.stdin.read(1)
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old)
                    return ch
        except Exception:
            use_live = False

    if not use_live:
        res = prompt(text, default, hint_text=hint_text)
        if live_formatter:
            try:
                formatted = live_formatter(res)
                if formatted:
                    print(f"     → {formatted}")
            except Exception:
                pass
        return res

    default_display = _c(C["dim"], f" ({default})") if default else ""
    print(f"  {_c(C['bold'], text)}{default_display}")
    if hint_text:
        print(_c(C["dim"], f"     {hint_text}"))
        
    input_str = ""
    sys.stdout.write(_c(C["magenta"], "  ❯ ") + _c(C["dim"], default))
    sys.stdout.flush()
    
    is_default = True
    
    while True:
        try:
            ch = get_char()
        except KeyboardInterrupt:
            print()
            raise KeyboardInterrupt
            
        if not ch:
            continue
            
        if ch == "\x03":
            print()
            raise KeyboardInterrupt
            
        if ch in ("\r", "\n"):
            break
            
        if ch in ("\x7f", "\x08"):
            if is_default:
                input_str = ""
                is_default = False
            elif len(input_str) > 0:
                input_str = input_str[:-1]
        elif ch.isprintable():
            if is_default:
                input_str = ""
                is_default = False
            input_str += ch
            
        sys.stdout.write("\r\x1b[K")
        sys.stdout.flush()
        
        live_hint = ""
        if live_formatter:
            try:
                val_to_format = input_str if input_str else default
                live_hint = live_formatter(val_to_format)
            except Exception:
                pass
                
        hint_display = f"   {_c(C['green'], '→ ' + live_hint)}" if live_hint else ""
        
        if is_default:
            sys.stdout.write(_c(C["magenta"], "  ❯ ") + _c(C["dim"], default) + hint_display)
        else:
            sys.stdout.write(_c(C["magenta"], "  ❯ ") + input_str + hint_display)
        sys.stdout.flush()
        
    print()
    val = input_str if input_str else default
    return val


def prompt_int(
    text: str,
    default: int,
    *,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
    hint_text: str = "",
    live_formatter = None,
) -> int:
    while True:
        raw = prompt_live(text, str(default), hint_text=hint_text, live_formatter=live_formatter)
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


def prompt_float(
    text: str,
    default: float,
    *,
    hint_text: str = "",
    live_formatter = None,
) -> float:
    while True:
        raw = prompt_live(text, str(default), hint_text=hint_text, live_formatter=live_formatter)
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
                    _c(C["cyan"], f"\r\n╭{bar}╮\r\n")
                    + _c(C["cyan"], "│")
                    + _c(C["bold"], header_text.center(width - 2))
                    + _c(C["cyan"], "│\r\n")
                    + _c(C["cyan"], f"╰{bar}╯\r\n\r\n")
                )
            sys.stdout.write(f"  {text}:\r\n")
            if hint_text:
                sys.stdout.write(_c(C["dim"], f"     {hint_text}") + "\r\n")
            sys.stdout.write("\r\n")
            for i, opt in enumerate(options):
                sel = opt in selected
                mark = _c(C["green"], "[x]") if sel else _c(C["dim"], "[ ]")
                pointer = _c(C["cyan"], " ›") if i == cursor else "  "
                sys.stdout.write(f"  {pointer} {mark} {opt}\r\n")
            sys.stdout.write("\r\n")
            # Navigation hints on one line, action keys on another if present.
            nav = f"  {_c(C['dim'], '↑↓/jk')} navigate   {_c(C['dim'], 'space')} toggle   {_c(C['dim'], 'enter')} confirm   {_c(C['dim'], 'a')} all  {_c(C['dim'], 'n')} none"
            sys.stdout.write(nav + "\r\n")
            if action_keys:
                ak = "   ".join(
                    f"{_c(C['dim'], k)} {v}" for k, v in action_keys.items()
                )
                sys.stdout.write(f"  {ak}\r\n")
            sys.stdout.flush()

        try:
            tty.setraw(fd)
            _redraw()
            while True:
                ch = sys.stdin.read(1)

                # ── Ctrl+C / Ctrl+D ──
                if ch == "\x03":
                    raise KeyboardInterrupt
                elif ch == "\x04":
                    raise EOFError

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
        "target_os": c.target_os,
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
        "use_legacy_key_tracking": c.use_legacy_key_tracking,
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
        elif not k.startswith("_") and k not in ("MAIN_SESSION", "PRACTICE_SESSION", "ONLINE_TRAINING_SESSION", "DEFAULT_SESSION"):
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
    source = cfg_path.read_text(encoding="utf-8")
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
                rf'^{name}\s*=\s*\{{.*?\}}',
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
    cfg_path.write_text(source, encoding="utf-8")


def _write_laser_task_config(updates: Dict[str, Any]) -> None:
    cfg_path = PROJECT_ROOT / "laserTask" / "config.py"
    source = cfg_path.read_text(encoding="utf-8")

    field_map = {
        "target_os": "target_os",
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
        "use_legacy_key_tracking": "use_legacy_key_tracking",
    }

    # Handle window_size specially
    if "window_size_w" in updates and "window_size_h" in updates:
        new_val = f"({updates['window_size_w']}, {updates['window_size_h']})"
        source = re.sub(
            r'^([ \t]*window_size:\s*[^=\n]+\s*=\s*)(.*?)(?=\n[ \t]*(?:[a-zA-Z_]\w*\s*:|#|"""|\'\'\'|@|class\s|def\s|$))',
            rf'\g<1>{new_val}',
            source,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
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
            rf'^([ \t]*{field_name}:\s*[^=\n]+\s*=\s*)(.*?)(?=\n[ \t]*(?:[a-zA-Z_]\w*\s*:|#|"""|\'\'\'|@|class\s|def\s|$))',
            rf'\g<1>{new_val}',
            source,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )
    cfg_path.write_text(source, encoding="utf-8")


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
    cfg["target_os"] = target_os
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

    current_os = cfg.get("target_os", detect_os())
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
        "Left / Counter-clockwise rotation key",
        cfg.get("key_left", "f"),
        hint_text="Keyboard key or response box button to rotate the shield counter-clockwise (left/CCW)",
    )
    cfg["key_right"] = prompt(
        "Right / Clockwise rotation key",
        cfg.get("key_right", "j"),
        hint_text="Keyboard key or response box button to rotate the shield clockwise (right/CW)",
    )
    cfg["use_legacy_key_tracking"] = prompt_yn(
        "Use legacy key tracking",
        cfg.get("use_legacy_key_tracking", False),
        hint_text="Yes = original Psychopy behavior (releases stop shield immediately); No = multi-key tracking (smooth)",
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
        osdef = OS_DEFAULTS.get(cfg.get("target_os", "linux"), OS_DEFAULTS["linux"])
        curr_os_default = OS_DEFAULTS.get(detect_os(), {}).get("serial_port")
        offered_default = cfg.get("serial_port")
        if offered_default == curr_os_default and detect_os() != cfg.get("target_os"):
            offered_default = osdef["serial_port"]

        cfg["serial_port"] = prompt(
            "Serial port",
            offered_default or osdef["serial_port"],
            hint_text=osdef["serial_hint"],
        )
        cfg["serial_baud_rate"] = prompt_int(
            "Baud rate",
            cfg.get("serial_baud_rate", 115200),
            hint_text="115200 for BrainVision TriggerBox",
        )
    elif mode == "parallel":
        osdef = OS_DEFAULTS.get(cfg.get("target_os", "linux"), OS_DEFAULTS["linux"])
        if osdef["parallel_addr"] is None:
            warn(f"Parallel ports are not supported on {cfg.get('target_os', 'linux')}.")
            cfg["trigger_mode"] = "dummy"
            info("Falling back to dummy trigger mode.")
        else:
            curr_os_default = OS_DEFAULTS.get(detect_os(), {}).get("parallel_addr")
            offered_default = cfg.get("parallel_address")
            if offered_default == curr_os_default and detect_os() != cfg.get("target_os"):
                offered_default = osdef["parallel_addr"]

            cfg["parallel_address"] = prompt(
                "Parallel port address",
                offered_default or osdef["parallel_addr"],
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
    available_fields = ["participant", "visit", "session", "order", "framing", "practice_only"]
    current_fields = cfg.get("dialog_fields", ["participant", "visit", "session", "order", "framing"])

    cfg["dialog_fields"], _ = prompt_multiselect(
        "Which fields should appear in the session dialog?",
        available_fields,
        defaults=current_fields,
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
    sr = stimgen.get("SAMPLE_RATE", 60)

    def frames_live_formatter(val_str: str) -> str:
        try:
            val = float(val_str)
            frames = val * sr
            if frames.is_integer():
                return f"{int(frames)} frames at {sr} Hz"
            return f"{frames:.1f} frames at {sr} Hz"
        except Exception:
            return ""

    def total_time_formatter(n_blocks=None, block_dur=None):
        def _fmt(val_str: str) -> str:
            try:
                val = float(val_str)
                if n_blocks is not None:
                    total = n_blocks * val
                    return f"Total time: {total:g} min (with {n_blocks} blocks)"
                elif block_dur is not None:
                    total = int(val) * block_dur
                    return f"Total time: {total:g} min (at {block_dur} min/block)"
                return ""
            except Exception:
                return ""
        return _fmt

    # ── practice ──
    ps = stimgen.get("PRACTICE_SESSION", {})
    print()
    info(_c(C["bold"], "Practice session (Jump design)"))
    curr_n = ps.get("nBlocks", 4)
    curr_dur = ps.get("blockDurationMin", 1)
    stimgen["_practice_block_dur"] = prompt_int(
        "  Block duration (min)",
        curr_dur, min_val=1,
        hint_text="Minutes per block",
        live_formatter=total_time_formatter(n_blocks=curr_n),
    )
    updated_dur = stimgen.get("_practice_block_dur", curr_dur)
    stimgen["_practice_n_blocks"] = prompt_int(
        "  Number of blocks",
        curr_n, min_val=1, max_val=20,
        hint_text="How many blocks for this session",
        live_formatter=total_time_formatter(block_dur=updated_dur),
    )

    # ── main / baseline ──
    ms = stimgen.get("MAIN_SESSION", {})
    print()
    info(_c(C["bold"], "Main & baseline sessions (Jump design)"))
    curr_n = ms.get("nBlocks", 12)
    curr_dur = ms.get("blockDurationMin", 3)
    stimgen["_main_block_dur"] = prompt_int(
        "  Block duration (min)",
        curr_dur, min_val=1,
        hint_text="Minutes per block",
        live_formatter=total_time_formatter(n_blocks=curr_n),
    )
    updated_dur = stimgen.get("_main_block_dur", curr_dur)
    stimgen["_main_n_blocks"] = prompt_int(
        "  Number of blocks (main)",
        curr_n, min_val=1, max_val=30,
        hint_text="How many blocks for this session",
        live_formatter=total_time_formatter(block_dur=updated_dur),
    )

    # ── common ──
    print()
    info(_c(C["bold"], "Common parameters (all session types)"))
    stimgen["NOISE_STD_LOW"] = prompt_int(
        "  Observation noise — low (°)",
        stimgen.get("NOISE_STD_LOW", 10), min_val=1,
    )
    stimgen["NOISE_STD_HIGH"] = prompt_int(
        "  Observation noise — high (°)",
        stimgen.get("NOISE_STD_HIGH", 20), min_val=1,
    )
    stimgen["JUMP_DURATION_MIN_SEC"] = prompt_float(
        "  Min jump duration (s)",
        stimgen.get("JUMP_DURATION_MIN_SEC", 0.1),
        hint_text="Minimum time the true mean stays in one position (default: 0.1 s)",
        live_formatter=frames_live_formatter,
    )
    stimgen["JUMP_DURATION_MEAN_SEC"] = prompt_float(
        "  Mean jump duration (s)",
        stimgen.get("JUMP_DURATION_MEAN_SEC", 0.3),
        hint_text="Average time the true mean stays in one position (default: 0.3 s)",
        live_formatter=frames_live_formatter,
    )
    stimgen["JUMP_DURATION_MAX_SEC"] = prompt_float(
        "  Max jump duration (s)",
        stimgen.get("JUMP_DURATION_MAX_SEC", 1.0),
        hint_text="Maximum time the true mean stays in one position (default: 1.0 s)",
        live_formatter=frames_live_formatter,
    )

    cfg["_stimgen_updates"] = stimgen
    return cfg


# ── summary table ───────────────────────────────────────────────────────────

def _kv(label: str, value: Any, suffix: str = "") -> str:
    s = str(value)
    label_text = f"{label}:"
    padded_label = label_text.ljust(20)
    return f"  {_c(C['dim'], padded_label)} {_c(C['bold'], s)}{suffix}"


def show_summary(cfg: Dict[str, Any], section_id: Optional[str] = None) -> None:
    if section_id is not None:
        section(f"Section {section_id} Summary")
    else:
        section("Configuration Summary")

    width = 59
    print(_c(C["cyan"], f"  ┌{'─' * (width - 4)}┐"))

    fullscr = "fullscreen" if cfg.get("fullscreen") else f"{cfg.get('window_size_w', '?')}×{cfg.get('window_size_h', '?')}"
    items = [
        # (label, value, section_id)
        ("Target OS", cfg.get("target_os", detect_os()), "1"),
        ("Monitor", f"{cfg.get('monitor_name', '?')} ({fullscr})", "1"),
        ("Screen index", cfg.get("screen_index", "?"), "1"),
        ("Refresh rate", f"{cfg.get('target_refresh_rate', '?')} Hz", "1"),
        ("Input", f"{cfg.get('input_device', '?')}  ({cfg.get('key_left', '?')} / {cfg.get('key_right', '?')})", "2"),
        ("  Legacy tracking", "Yes" if cfg.get("use_legacy_key_tracking") else "No", "2"),
        ("Triggers", cfg.get("trigger_mode", "?"), "3"),
    ]
    if cfg.get("trigger_mode") == "serial":
        items.append(("  Serial port", cfg.get("serial_port", "?"), "3"))
        items.append(("  Baud rate", cfg.get("serial_baud_rate", "?"), "3"))
    elif cfg.get("trigger_mode") == "parallel":
        items.append(("  Parallel addr", cfg.get("parallel_address", "?"), "3"))

    # Read current stimgen configuration values
    stimgen = _read_stimgen_config()
    # Merge in any pending/unsaved updates in memory
    stimgen_updates = cfg.get("_stimgen_updates") or {}

    # Resolve values
    main_n = stimgen_updates.get("_main_n_blocks", stimgen.get("MAIN_SESSION", {}).get("nBlocks", "?"))
    main_dur = stimgen_updates.get("_main_block_dur", stimgen.get("MAIN_SESSION", {}).get("blockDurationMin", "?"))
    prac_n = stimgen_updates.get("_practice_n_blocks", stimgen.get("PRACTICE_SESSION", {}).get("nBlocks", "?"))
    prac_dur = stimgen_updates.get("_practice_block_dur", stimgen.get("PRACTICE_SESSION", {}).get("blockDurationMin", "?"))
    noise_low = stimgen_updates.get("NOISE_STD_LOW", stimgen.get("NOISE_STD_LOW", "?"))
    noise_high = stimgen_updates.get("NOISE_STD_HIGH", stimgen.get("NOISE_STD_HIGH", "?"))
    jump_min = stimgen_updates.get("JUMP_DURATION_MIN_SEC", stimgen.get("JUMP_DURATION_MIN_SEC", "?"))
    jump_mean = stimgen_updates.get("JUMP_DURATION_MEAN_SEC", stimgen.get("JUMP_DURATION_MEAN_SEC", "?"))
    jump_max = stimgen_updates.get("JUMP_DURATION_MAX_SEC", stimgen.get("JUMP_DURATION_MAX_SEC", "?"))

    items += [
        ("Run blocks", f"{cfg.get('n_blocks', '?')} main" + (" + practice" if cfg.get("enable_practice") else ""), "4"),
        ("Gen practice", f"{prac_n} blocks @ {prac_dur} min", "7"),
        ("Gen main", f"{main_n} blocks @ {main_dur} min", "7"),
        ("Gen noise (L/H)", f"{noise_low}° / {noise_high}°", "7"),
        ("Gen jump range", f"{jump_min}s - {jump_max}s (mean: {jump_mean}s)", "7"),
        ("Shield", f"{'adjustable' if cfg.get('allow_shield_adjustment') else 'fixed'}  ({cfg.get('rotation_speed', '?')}°/frame, r={cfg.get('circle_radius', '?')})", "5"),
        ("Loss factor", f"{cfg.get('loss_factor', '?')}  ({cfg.get('currency_symbol', '?')})", "5"),
        ("Min laser dur", f"{cfg.get('min_laser_duration_frames', '?')} frames", "5"),
    ]

    if cfg.get("enable_audio"):
        items += [
            ("Tones", f"{cfg.get('tone_freq_standard', '?')} / {cfg.get('tone_freq_deviant', '?')} Hz", "6"),
            ("Tone dur / ISI", f"{cfg.get('tone_duration', '?')*1000:.0f} ms / {cfg.get('tone_isi_frames', '?')} frames", "6"),
            ("Tone volume", cfg.get("tone_volume", "?"), "6"),
        ]
    else:
        items.append(("Tones", _c(C["dim"], "disabled"), "6"))

    items += [
        ("Seq version", f"main={SEQUENCE_VERSION}, practice={PRACTICE_SEQUENCE_VERSION}", "8"),
        ("Visits", f"{', '.join(cfg.get('visits', ['?']))}", "8"),
        ("Sessions", f"{', '.join(cfg.get('sessions', ['?']))}", "8"),
        ("Orders", f"{', '.join(cfg.get('orders', ['?']))}", "8"),
        ("Framings", f"{', '.join(cfg.get('framings', ['?']))}", "8"),
    ]

    # Filter by section_id if provided
    if section_id is not None:
        items = [x for x in items if x[2] == section_id]

    for label, value, _ in items:
        line = _kv(label, value)
        visible_len = len(re.sub(r'\033\[[0-9;]*m', '', line))
        padding = max(0, (width - 4) - visible_len)
        print(_c(C["cyan"], "  │") + line + " " * padding + _c(C["cyan"], "│"))

    print(_c(C["cyan"], f"  └{'─' * (width - 4)}┘"))
    print()


# ── sequence generation ─────────────────────────────────────────────────────

def run_sequence_generation(cfg: Dict[str, Any]) -> bool:
    section("Generating Sequences")

    if prompt_yn("Delete existing sequence files before generating new ones?", default=False):
        import shutil
        seq_dir = PROJECT_ROOT / "sequences"
        if seq_dir.is_dir():
            info(f"Deleting old generated files in {seq_dir} …")
            deleted_count = 0
            for ext in ["*.csv", "*.png", "*.pkl"]:
                for file_path in seq_dir.rglob(ext):
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except Exception as e:
                        fail(f"Could not delete {file_path}: {e}")
            success(f"Deleted {deleted_count} old generated files")

    _save_stimgen_from_cfg(cfg)

    # Laser sequences
    info("Generating laser stimulus sequences …")
    laser_dir = PROJECT_ROOT / "stimgen" / "laser"
    result = subprocess.run(
        [sys.executable, "coin_script_sequence_generation.py"],
        cwd=str(laser_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
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
    mmn_out = (PROJECT_ROOT / "sequences" / "mmn").as_posix()
    result = subprocess.run(
        [
            sys.executable, "-c",
            f"from stimgen.mmn.generate_all_peduks_sessions import generate_all_peduks_sessions; "
            f"generate_all_peduks_sessions('{mmn_out}')",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
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
    """Interactive menu — numbered single-select sections + action keys."""
    dirty = False

    while True:
        clear()
        header("CoIn Laser Task — Setup")

        if dirty:
            print(_c(C["yellow"], "  ← unsaved changes in memory"))
            print()

        print("  Sections to configure:\n")
        for slug, desc, _ in SECTION_REGISTRY:
            print(f"    {_c(C['green'], slug)})  {desc}")

        print()
        print(f"  {_c(C['cyan'], 's')})  Show current configuration")
        print(f"  {_c(C['cyan'], 'g')})  Generate sequences")
        print(f"  {_c(C['cyan'], 'r')})  Run experiment" + _c(C["dim"], "  (python main.py)"))
        print(f"  {_c(C['dim'], 'q')})  Quit & save")

        print()
        choice = input(_c(C["magenta"], "  ❯ ")).strip().lower()

        if choice == "q":
            break
        elif choice == "s":
            show_summary(cfg)
        elif choice == "r":
            if dirty:
                warn("Unsaved config changes — run anyway?")
                if not prompt_yn("Proceed without saving?", True):
                    continue
            print()
            info("Launching experiment …")
            print()
            subprocess.run([sys.executable, str(PROJECT_ROOT / "main.py")])
            return
        elif choice == "g":
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
        elif choice in SECTION_MAP:
            desc, fn = SECTION_MAP[choice]
            cfg = fn(cfg)
            dirty = True
            show_summary(cfg, choice)
            if prompt_yn("Save this section?", True):
                _write_laser_task_config(cfg)
                _save_stimgen_from_cfg(cfg.copy())
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
            _save_stimgen_from_cfg(cfg.copy())
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
