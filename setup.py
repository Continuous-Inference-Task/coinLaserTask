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
sys.path.insert(0, str(PROJECT_ROOT / "stimgen" / "laser"))

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


class GoBack(Exception):
    """Raised when the user wants to return to the previous menu."""
    pass


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
        print(_c(C["dim"], "     (type 'back' to return to menu)"))
        raw = input(_c(C["magenta"], "  ❯ ")).strip()

        # ── back to menu ──
        if raw.lower() in ("back", "cancel"):
            print()
            confirm = input(
                _c(C["yellow"], "  Go back to menu? Current section inputs will be lost. [Y/n] ")
            ).strip().lower()
            if confirm in ("", "y", "yes"):
                raise GoBack()
            print()
            continue

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


def prompt_options(
    text: str,
    choices: List[str],
    default: str = "",
    labels: Optional[Dict[str, str]] = None,
    hint_text: str = "",
) -> str:
    """Ask the user to choose from a list of options with optional custom labels."""
    labels = labels or {}
    for i, choice in enumerate(choices, 1):
        desc = labels.get(choice, choice)
        marker = _c(C["green"], "→") if choice == default else " "
        print(f"     {marker} {i}. {desc}")
    print()

    while True:
        default_display = _c(C["dim"], f" ({default})") if default else ""
        print(f"  {_c(C['bold'], text)}{default_display}")
        if hint_text:
            print(_c(C["dim"], f"     {hint_text}"))
        print(_c(C["dim"], "     (type 'back' to return to menu)"))
        raw = input(_c(C["magenta"], "  ❯ ")).strip()

        if raw.lower() in ("back", "cancel"):
            print()
            confirm = input(
                _c(C["yellow"], "  Go back to menu? Current section inputs will be lost. [Y/n] ")
            ).strip().lower()
            if confirm in ("", "y", "yes"):
                raise GoBack()
            print()
            continue

        val = raw if raw else default

        if val in choices:
            return val
        if val.isdigit() and 1 <= int(val) <= len(choices):
            return choices[int(val) - 1]
            
        warn(f"Invalid option. Please enter a number (1-{len(choices)}) or type the choice exactly.")
        print()


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
    print(_c(C["dim"], "     (type 'back' to return to menu)"))
        
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

    # ── back to menu ──
    if val.lower() in ("back", "cancel"):
        confirm = input(
            _c(C["yellow"], "  Go back to menu? Current inputs will be lost. [Y/n] ")
        ).strip().lower()
        if confirm in ("", "y", "yes"):
            raise GoBack()
        return val

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
            nav = f"  {_c(C['dim'], '↑↓/jk')} navigate   {_c(C['dim'], 'space')} toggle   {_c(C['dim'], 'enter')} confirm   {_c(C['dim'], 'a')} all  {_c(C['dim'], 'n')} none  {_c(C['dim'], 'b')} back"
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

                # ── b = back ──
                elif ch == "b":
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
                    sys.stdout.write("\033[H\033[2J")
                    sys.stdout.flush()
                    return sorted(selected, key=lambda o: options.index(o)), "b"

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
            print(_c(C["dim"], f"  Actions: {ak}, 'a'=all, 'n'=none, 'b'=back"))
        else:
            print(_c(C["dim"], "  'a'=all, 'n'=none, 'b'=back"))
        raw = input(f"  {_c(C['bold'], '>')} ").strip().lower()

        if not raw:
            return sorted(selected, key=lambda o: options.index(o)), None
        if action_keys and raw in action_keys:
            return sorted(selected, key=lambda o: options.index(o)), raw
        if raw == "b":
            return sorted(selected, key=lambda o: options.index(o)), "b"
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
        "fixed_shield_degrees": c.fixed_shield_degrees,
        "loss_factor": c.loss_factor,
        "currency_symbol": c.currency_symbol,
        "trigger_mode": c.trigger_mode,
        "serial_port": c.serial_port,
        "serial_baud_rate": c.serial_baud_rate,
        "parallel_address": c.parallel_address,
        "enable_audio": c.enable_audio,
        "show_earth_background": c.show_earth_background,
        "tone_freq_standard": c.tone_freq_standard,
        "tone_freq_deviant": c.tone_freq_deviant,
        "tone_duration": c.tone_duration,
        "tone_duration_standard": c.tone_duration_standard,
        "tone_duration_deviant": c.tone_duration_deviant,
        "tone_volume": c.tone_volume,
        "tone_isi_frames": c.tone_isi_frames,
        "enable_practice": c.enable_practice,
        "reset_reward_after_practice": c.reset_reward_after_practice,
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
    """Read stimgen/laser/config.py via direct import, reloading all potential caches."""
    import sys
    import importlib

    # 1. Reload the config modules
    for name in ["config", "stimgen.laser.config"]:
        if name in sys.modules:
            try:
                importlib.reload(sys.modules[name])
            except Exception:
                pass
        else:
            try:
                importlib.import_module(name)
            except Exception:
                pass

    # 2. Reload the design modules that depend on config
    for name in [
        "design_vola_stocha",
        "stimgen.laser.design_vola_stocha",
        "design_vola_stocha_random_walk",
        "stimgen.laser.design_vola_stocha_random_walk"
    ]:
        if name in sys.modules:
            try:
                importlib.reload(sys.modules[name])
            except Exception:
                pass

    from stimgen.laser import config as _cfg
    importlib.reload(_cfg)
    return {
        "SAMPLE_RATE": _cfg.SAMPLE_RATE,
        "JUMP_DURATION_MEAN_SEC": _cfg.JUMP_DURATION_MEAN_SEC,
        "JUMP_DURATION_MIN_SEC": _cfg.JUMP_DURATION_MIN_SEC,
        "JUMP_DURATION_MAX_SEC": _cfg.JUMP_DURATION_MAX_SEC,
        "JUMP_VALUE_SET": _cfg.JUMP_VALUE_SET,
        "VOLATILITY_PRESETS": dict(_cfg.VOLATILITY_PRESETS),
        "NOISE_PRESETS": dict(_cfg.NOISE_PRESETS),
        "SAVED_DESIGNS": dict(_cfg.SAVED_DESIGNS),
        "PRACTICE_VOLATILITY": list(_cfg.PRACTICE_VOLATILITY),
        "PRACTICE_NOISE": list(_cfg.PRACTICE_NOISE),
        "PRACTICE_NOISE_MODE": _cfg.PRACTICE_NOISE_MODE,
        "PRACTICE_N_SESSIONS": _cfg.PRACTICE_N_SESSIONS,
        "PRACTICE_BLOCK_DURATION_MIN": _cfg.PRACTICE_BLOCK_DURATION_MIN,
        "MAIN_VOLATILITY": list(_cfg.MAIN_VOLATILITY),
        "MAIN_NOISE": list(_cfg.MAIN_NOISE),
        "MAIN_NOISE_MODE": _cfg.MAIN_NOISE_MODE,
        "MAIN_N_SESSIONS": _cfg.MAIN_N_SESSIONS,
        "MAIN_BLOCK_DURATION_MIN": _cfg.MAIN_BLOCK_DURATION_MIN,
    }


def _save_stimgen_from_cfg(cfg: Dict[str, Any]) -> bool:
    """Write stimgen config if there are pending updates in cfg."""
    stimgen_updates = cfg.pop("_stimgen_updates", None)
    if not stimgen_updates:
        return True

    try:
        _write_stimgen_config(stimgen_updates)
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
                elif isinstance(dv, list):
                    inner = ", ".join(repr(x) for x in dv)
                    lines.append(f'    "{dk}": [{inner}],')
                else:
                    lines.append(f'    "{dk}": {dv},')
            lines.append("}")
            replacement = "\n".join(lines)
            source = re.sub(
                rf'^{name}\s*=\s*\{{.*?^\s*\}}',
                replacement,
                source,
                flags=re.MULTILINE | re.DOTALL,
            )
        elif isinstance(value, list):
            inner = ", ".join(repr(x) for x in value)
            new_val = f"[{inner}]"
            source = re.sub(
                rf'^({name}\s*=\s*).+?(\s*(?:#.*)?)$',
                rf'\g<1>{new_val}\g<2>',
                source,
                flags=re.MULTILINE,
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
        "fixed_shield_degrees": "fixed_shield_degrees",
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
        "tone_duration_standard": "tone_duration_standard",
        "tone_duration_deviant": "tone_duration_deviant",
        "tone_volume": "tone_volume",
        "tone_isi_frames": "tone_isi_frames",
        "enable_practice": "enable_practice",
        "reset_reward_after_practice": "reset_reward_after_practice",
        "show_earth_background": "show_earth_background",
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

    cfg["enable_practice"] = prompt_yn(
        "Include practice block?",
        cfg.get("enable_practice", True),
        hint_text="Shown before the main blocks; good for first-time participants",
    )

    cfg["show_earth_background"] = prompt_yn(
        "Show earth/world background behind the game?",
        cfg.get("show_earth_background", True),
        hint_text="If disabled, a plain black background is shown instead",
    )

    cfg["reset_reward_after_practice"] = prompt_yn(
        "Reset reward counter after practice?",
        cfg.get("reset_reward_after_practice", True),
        hint_text="If yes, the reward bar resets to zero when the main session starts",
    )
    return cfg


def _derive_sessions_and_orders() -> Tuple[List[str], List[str]]:
    """Derive session and order dropdown values from stimgen config.

    Sessions = MAIN_N_SESSIONS (how many full balanced sets to run).
    Orders   = always ["1","2","3","4"] (all counterbalance orders).
    """
    stimgen = _read_stimgen_config()
    n_sessions = stimgen.get("MAIN_N_SESSIONS", 3)
    return [str(i) for i in range(1, n_sessions + 1)], ["1", "2", "3", "4"]


def configure_dialog(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Startup Dialog Options")

    # ── which fields appear (interactive multiselect) ──
    available_fields = ["participant", "visit", "session", "order", "framing", "practice_mode"]
    current_fields = cfg.get("dialog_fields", ["participant", "visit", "session", "order", "framing"])

    cfg["dialog_fields"], action = prompt_multiselect(
        "Which fields should appear in the session dialog?",
        available_fields,
        defaults=current_fields,
    )
    if action == "b":
        raise GoBack()

    # Always force-include participant (required for data files)
    if "participant" not in cfg["dialog_fields"]:
        cfg["dialog_fields"] = ["participant"] + cfg["dialog_fields"]
        info("'participant' was force-included (required for data-file naming).")

    # ── sessions & orders: auto-derived from sequence generation config ──
    derived_sessions, derived_orders = _derive_sessions_and_orders()
    cfg["sessions"] = derived_sessions
    cfg["orders"] = derived_orders

    stimgen = _read_stimgen_config()
    main_vol = stimgen.get("MAIN_VOLATILITY", ["stable", "volatile"])
    main_noise = stimgen.get("MAIN_NOISE", ["precise", "noisy"])
    main_types = len(main_vol) * len(main_noise)
    main_n_sessions = stimgen.get("MAIN_N_SESSIONS", 3)

    print()
    info(_c(C["bold"], "Dropdown values (auto-detected from sequence generation config):"))
    info(f"  Sessions:  {', '.join(derived_sessions):20s} " + _c(C["dim"], f"({main_n_sessions} session{'s' if main_n_sessions != 1 else ''}, {main_types} block types/session)"))
    info(f"  Orders:    {', '.join(derived_orders):20s} " + _c(C["dim"], "(all 4 counterbalancing orders always generated)"))

    cfg["visits"] = cfg.get("visits", ["1", "2"])
    cfg["framings"] = cfg.get("framings", ["loss", "win"])

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

    if not cfg.get("allow_shield_adjustment", False):
        cfg["fixed_shield_degrees"] = prompt_float(
            "Fixed shield size (half-width in degrees)",
            cfg.get("fixed_shield_degrees", 20.0),
            hint_text="Degrees — angular half-width of the shield (Peduks/MMN: 20.0, CogPsy: 40.0)",
        )

    cfg["rotation_speed"] = prompt_float(
        "Shield rotation speed",
        cfg.get("rotation_speed", 1.0),
        hint_text="Degrees per frame — how fast the shield moves when a key is held (Peduks Study: 1.0)",
    )
    cfg["circle_radius"] = prompt_float(
        "Circle radius",
        cfg.get("circle_radius", 3.0),
        hint_text="PsychoPy height units — size of the game circle (Peduks Study: 3.0)",
    )
    cfg["loss_factor"] = prompt_float(
        "Loss factor",
        cfg.get("loss_factor", 0.003),
        hint_text="Reward scaling multiplier applied to miss penalties (Peduks Study: 0.003)",
    )
    cfg["currency_symbol"] = prompt(
        "Currency symbol",
        cfg.get("currency_symbol", "£"),
        hint_text="Displayed to the participant (Peduks Study: £)",
    )

    cfg["min_laser_duration_frames"] = prompt_int(
        "Min laser duration (frames)",
        cfg.get("min_laser_duration_frames", 6),
        min_val=1,
        max_val=60,
        hint_text="Observations shorter than this are merged into the previous one (Peduks Study: 6 frames)",
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
        hint_text="Pitch of the frequent tone (Peduks Study: 440 Hz)",
    )
    cfg["tone_freq_deviant"] = prompt_float(
        "Deviant tone frequency (Hz)",
        cfg.get("tone_freq_deviant", 528.0),
        hint_text="Pitch of the rare tone (Peduks Study: 528 Hz)",
    )
    duration_ms = int(cfg.get("tone_duration", 0.07) * 1000)
    cfg["tone_duration"] = (
        prompt_int(
            "Base tone duration (ms)",
            duration_ms,
            min_val=10,
            max_val=500,
            hint_text="How long each tone plays by default (Peduks Study: 70 ms)",
        )
        / 1000.0
    )
    if prompt_yn("Customize standard vs. deviant durations separately?", False):
        std_dur_ms = int(cfg.get("tone_duration_standard", -1.0) * 1000)
        if std_dur_ms < 0:
            std_dur_ms = int(cfg["tone_duration"] * 1000)
        cfg["tone_duration_standard"] = (
            prompt_int(
                "Standard tone duration (ms)",
                std_dur_ms,
                min_val=10,
                max_val=500,
            )
            / 1000.0
        )
        dev_dur_ms = int(cfg.get("tone_duration_deviant", -1.0) * 1000)
        if dev_dur_ms < 0:
            dev_dur_ms = int(cfg["tone_duration"] * 1000)
        cfg["tone_duration_deviant"] = (
            prompt_int(
                "Deviant tone duration (ms)",
                dev_dur_ms,
                min_val=10,
                max_val=500,
            )
            / 1000.0
        )
    else:
        cfg["tone_duration_standard"] = -1.0
        cfg["tone_duration_deviant"] = -1.0

    cfg["tone_isi_frames"] = prompt_int(
        "Inter-stimulus interval (frames)",
        cfg.get("tone_isi_frames", 26),
        min_val=1,
        hint_text="Gap between tones in frames (Peduks Study: 26 frames)",
    )
    fps = cfg.get("target_refresh_rate", 60)
    info(f"  → Effective ISI: ~{cfg['tone_isi_frames'] / fps * 1000:.0f} ms at {fps} Hz")

    cfg["tone_volume"] = prompt_float(
        "Tone volume",
        cfg.get("tone_volume", 1.0),
        hint_text="0.0 = silent, 1.0 = full volume (Peduks Study: 1.0)",
    )
    return cfg


def _session_count_formatter(block_dur=None):
    """Live formatter showing session CSV count + total time."""
    def _fmt(val_str: str) -> str:
        try:
            n = int(val_str)
            sessions = (n + 3) // 4  # ceil(n/4), blocks_per_session=4
            parts = [f"{sessions} session CSV{'s' if sessions != 1 else ''} ({n} blocks ÷ 4/session)"]
            if block_dur is not None:
                parts.append(f"total: {n * block_dur} min")
            return "  →  ".join(parts)
        except Exception:
            return ""
    return _fmt


def _pick_presets(
    action_label: str,
    presets: Dict[str, Any],
    dimension_hint: str,
    allow_custom: bool = True,
    multiply_by: List[str] = None,
    noise_mode_holder: List[str] = None,
) -> List[str]:
    def _prompt_noise_mode():
        if not (multiply_by and len(set(multiply_by)) > 1 and noise_mode_holder):
            return
        options = ["counterbalanced"]
        labels = {
            "counterbalanced": "Counterbalanced (all noise levels × all volatility blocks)",
        }
        seen = set()
        unique_vols = []
        for v in multiply_by:
            if v not in seen:
                seen.add(v)
                unique_vols.append(v)
        for v in unique_vols:
            mode_name = f"{v}_only"
            options.append(mode_name)
            labels[mode_name] = f"Only apply noise levels to '{v}' blocks (others stay at base level)"
            
        current_mode = noise_mode_holder[0]
        if current_mode not in options:
            current_mode = "counterbalanced"
            
        is_practice = "practice" in action_label.lower()
        session_name = "Practice" if is_practice else "Main experiment"
        print()
        info(f"{session_name}: You have configured multiple volatility blocks and noise levels.")
        print()
        new_mode = prompt_options(
            f"{session_name} noise distribution mode",
            options,
            default=current_mode,
            labels=labels,
        )
        noise_mode_holder[0] = new_mode
    """Interactive preset picker — pick items one at a time to build a list."""
    print()
    hint(dimension_hint)
    print()
    info(_c(C["bold"], action_label))
    print()

    preset_names = list(presets.keys())
    selected: List[str] = []

    # Origin hints for known presets
    ORIGIN_HINTS = {
        "stable":   "CoIn / PEDUKS — slow mean jumps, ~10 s epochs",
        "volatile": "CoIn / PEDUKS — fast mean jumps, ~3 s epochs",
        "medium":   "CogPsy — intermediate speed, ~5 s epochs",
        "precise":  "CoIn / PEDUKS — tight observations, ±15°",
        "noisy":    "CoIn / PEDUKS — scattered observations, ±20°",
    }

    while True:
        noise_mode = noise_mode_holder[0] if noise_mode_holder else "counterbalanced"
        # Show available presets
        for i, name in enumerate(preset_names, 1):
            count = selected.count(name)
            already = _c(C["green"], f" (selected {count}x)") if count > 0 else ""
            val = presets[name]
            if isinstance(val, list):
                disp = _c(C["dim"], f"[{', '.join(str(v) for v in val)}]")
            else:
                disp = _c(C["dim"], str(val))
            hint_str = _c(C["dim"], f"  — {ORIGIN_HINTS.get(name, '')}") if name in ORIGIN_HINTS else ""
            print(f"    {_c(C['green'], str(i))}. {name:12s} {disp}{already}{hint_str}")

        if allow_custom:
            custom_num = len(preset_names) + 1
            print(f"    {_c(C['green'], str(custom_num))}. Custom — create a new preset")
        print()

        # Display selected sequence as beautiful ANSI blocks
        if selected:
            box_height = 3 if multiply_by else 1
            
            line_top = ""
            lines_mid = [""] * box_height
            line_bot = ""
            line_idx = ""
            
            # We separate noise level groups by 3 spaces
            group_sep = "   "
            
            for idx, name in enumerate(selected, 1):
                # Choose color based on the selected name
                color = C["green"]
                if name == "stable":
                    color = C["blue"]
                elif name == "volatile":
                    color = C["red"]
                elif name == "medium":
                    color = C["yellow"]
                elif name == "precise":
                    color = C["blue"]
                elif name == "noisy":
                    color = C["red"]
                
                if multiply_by:
                    group_boxes_top = []
                    group_boxes_mid = [[] for _ in range(box_height)]
                    group_boxes_bot = []
                    group_box_widths = []
                    
                    active_v = multiply_by
                    if noise_mode and noise_mode.endswith("_only") and idx > 1:
                        vola_only = noise_mode[:-5]
                        active_v = [v for v in multiply_by if v == vola_only]
                        
                    for v in active_v:
                        block_lines = [v, "x", name]
                        w = max(max(len(l) for l in block_lines), 6)
                        group_box_widths.append(w + 4)
                        
                        b_top = color + "┌" + "─" * (w + 2) + "┐" + C["reset"]
                        
                        b_m = []
                        for h_idx in range(box_height):
                            line_text = block_lines[h_idx]
                            padding = w - len(line_text)
                            pad_l = padding // 2
                            pad_r = padding - pad_l
                            b_m.append(color + "│ " + C["bold"] + " " * pad_l + line_text + " " * pad_r + C["reset"] + color + " │" + C["reset"])
                        
                        b_bot = color + "└" + "─" * (w + 2) + "┘" + C["reset"]
                        
                        group_boxes_top.append(b_top)
                        for h_idx in range(box_height):
                            group_boxes_mid[h_idx].append(b_m[h_idx])
                        group_boxes_bot.append(b_bot)
                    
                    g_top = " ".join(group_boxes_top)
                    g_mid = [" ".join(group_boxes_mid[h]) for h in range(box_height)]
                    g_bot = " ".join(group_boxes_bot)
                    
                    g_width = sum(group_box_widths) + (len(multiply_by) - 1)
                    
                    idx_str = f"({idx})"
                    idx_pad = g_width - len(idx_str)
                    idx_l = idx_pad // 2
                    idx_r = idx_pad - idx_l
                    g_idx = " " * idx_l + _c(C["dim"], idx_str) + " " * idx_r
                    
                else:
                    w = max(len(name), 6)
                    g_top = color + "┌" + "─" * (w + 2) + "┐" + C["reset"]
                    
                    g_mid = []
                    line_text = name
                    padding = w - len(line_text)
                    pad_l = padding // 2
                    pad_r = padding - pad_l
                    g_mid.append(color + "│ " + C["bold"] + " " * pad_l + line_text + " " * pad_r + C["reset"] + color + " │" + C["reset"])
                    
                    g_bot = color + "└" + "─" * (w + 2) + "┘" + C["reset"]
                    
                    g_width = w + 4
                    idx_str = f"({idx})"
                    idx_pad = g_width - len(idx_str)
                    idx_l = idx_pad // 2
                    idx_r = idx_pad - idx_l
                    g_idx = " " * idx_l + _c(C["dim"], idx_str) + " " * idx_r
                
                sep = "" if idx == 1 else group_sep
                line_top += sep + g_top
                for h_idx in range(box_height):
                    lines_mid[h_idx] += sep + g_mid[h_idx]
                line_bot += sep + g_bot
                line_idx += sep + g_idx
            
            if multiply_by:
                print("  Selected noise levels (multiplied with volatility blocks):")
            else:
                print("  Selected blocks sequence:")
            print("  " + line_top)
            for m_line in lines_mid:
                print("  " + m_line)
            print("  " + line_bot)
            print("  " + line_idx)
            print()

        if not selected:
            prompt_text = "Pick preset to add (number"
        else:
            prompt_text = "Pick preset to add (number, -position=remove"

        if allow_custom:
            prompt_text += ", c=create new, ↵ done"
        else:
            prompt_text += ", ↵ done"
        prompt_text += ")"

        # Print the prompt instruction before the input
        print(_c(C["dim"], f"  {prompt_text}"))
        raw = input(_c(C["magenta"], f"  ❯ ")).strip().lower()

        if not raw:
            if not selected:
                warn("Select at least one.")
                continue
            break

        # Handle removals starting with '-'
        if raw.startswith("-"):
            try:
                remove_idx = int(raw[1:]) - 1
                if 0 <= remove_idx < len(selected):
                    removed_name = selected.pop(remove_idx)
                    info(f"Removed '{removed_name}' at position {remove_idx + 1}")
                else:
                    warn(f"Invalid position to remove (1-{len(selected)})")
            except ValueError:
                warn("To remove a block, type '-' followed by its position number (e.g., -1)")
            continue

        custom_num = len(preset_names) + 1
        if allow_custom and (raw == "c" or raw == str(custom_num)):
            new_name = prompt("  Name for new preset", "").strip()
            if not new_name:
                continue
            if isinstance(list(presets.values())[0], list):
                raw_vals = prompt(
                    f"  Values [mean, std, min, max]",
                    ", ".join(str(v) for v in list(presets.values())[0]),
                    hint_text="Comma-separated: mean epoch duration, std, min, max",
                )
                try:
                    vals = [float(x.strip()) for x in raw_vals.split(",")]
                    if len(vals) != 4:
                        warn("Need exactly 4 values: mean, std, min, max")
                        continue
                except ValueError:
                    warn("Invalid numbers")
                    continue
                presets[new_name] = vals
            else:
                raw_val = prompt_float(f"  Noise std (degrees)", 20.0)
                presets[new_name] = raw_val
            preset_names.append(new_name)
            selected.append(new_name)
            success(f"Added '{new_name}'")
            _prompt_noise_mode()
            continue

        try:
            idx = int(raw) - 1
            if 0 <= idx < len(preset_names):
                name = preset_names[idx]
                selected.append(name)
                info(f"Added '{name}'")
                _prompt_noise_mode()
            else:
                max_num = len(preset_names) + 1 if allow_custom else len(preset_names)
                warn(f"Invalid number (1-{max_num})")
        except ValueError:
            max_num = len(preset_names) + 1 if allow_custom else len(preset_names)
            warn(f"Enter a number (1-{max_num}), '-' followed by position to remove, or ↵ to finish")

    print()
    return selected


def _print_combinations_summary(
    vol_list: List[str],
    noise_list: List[str],
    v_presets: Dict[str, Any],
    n_presets: Dict[str, Any],
    noise_mode: str = "counterbalanced",
) -> None:
    from design_vola_stocha import design_vola_stocha
    
    try:
        design = design_vola_stocha(vol_list, noise_list, noise_mode)
        block_types = design['blockTypes']
    except Exception:
        block_types = [f"{v}+{n}" for v in vol_list for n in noise_list]
        
    n_types = len(block_types)
    info(_c(C["bold"], f"→ {len(vol_list)} volatility × {len(noise_list)} noise ({noise_mode}) = {n_types} block type{'s' if n_types != 1 else ''}"))
    print(_c(C["dim"], "  ─────────────────────────────────────────────"))
    
    box_height = 3
    line_top = ""
    lines_mid = [""] * box_height
    line_bot = ""
    line_dur = ""
    line_noise = ""
    
    for box_idx, b_type in enumerate(block_types, 1):
        if "+" in b_type:
            v, n = b_type.split("+")
        else:
            v, n = b_type, ""
            
        color = C["green"]
        if v == "stable" and n == "precise":
            color = C["blue"]
        elif v == "stable" and n == "noisy":
            color = C["cyan"]
        elif v == "volatile" and n == "precise":
            color = C["yellow"]
        elif v == "volatile" and n == "noisy":
            color = C["red"]
        elif v == "stable":
            color = C["blue"]
        elif v == "volatile":
            color = C["red"]
            
        block_lines = [v, "x", n] if n else [v]
        w = max(max(len(l) for l in block_lines), 11)
        
        b_top = color + "┌" + "─" * (w + 2) + "┐" + C["reset"]
        
        b_m = []
        for h_idx in range(box_height):
            if h_idx < len(block_lines):
                line_text = block_lines[h_idx]
            else:
                line_text = ""
            padding = w - len(line_text)
            pad_l = padding // 2
            pad_r = padding - pad_l
            b_m.append(color + "│ " + C["bold"] + " " * pad_l + line_text + " " * pad_r + C["reset"] + color + " │" + C["reset"])
        
        b_bot = color + "└" + "─" * (w + 2) + "┘" + C["reset"]
        
        v_val = v_presets.get(v, [0])
        v_mean = v_val[0] if isinstance(v_val, list) else v_val
        n_val = n_presets.get(n, 0) if n else 0
        
        dur_str = f"epoch: ~{v_mean}s"
        noise_str = f"noise: ±{n_val}°"
        
        box_w_total = w + 4
        
        d_pad = box_w_total - len(dur_str)
        d_pad_l = max(0, d_pad // 2)
        d_pad_r = max(0, d_pad - d_pad_l)
        d_line = " " * d_pad_l + _c(C["dim"], dur_str) + " " * d_pad_r
        
        n_pad = box_w_total - len(noise_str)
        n_pad_l = max(0, n_pad // 2)
        n_pad_r = max(0, n_pad - n_pad_l)
        n_line = " " * n_pad_l + _c(C["dim"], noise_str) + " " * n_pad_r
        
        sep = "" if box_idx == 1 else "  "
        line_top += sep + b_top
        for h_idx in range(box_height):
            lines_mid[h_idx] += sep + b_m[h_idx]
        line_bot += sep + b_bot
        line_dur += sep + d_line
        line_noise += sep + n_line
        
    print("  " + line_top)
    for m_line in lines_mid:
        print("  " + m_line)
    print("  " + line_bot)
    print("  " + line_dur)
    print("  " + line_noise)
    print()


def configure_stimgen(cfg: Dict[str, Any]) -> Dict[str, Any]:
    section("Block Design & Sequence Generation")
    info("Block types are defined by two independent dimensions:")
    info("  • Volatility — how fast the laser's true position jumps (epoch duration)")
    info("  • Noise      — how much observation noise is added (std dev in degrees)")
    info("Each session = one full balanced set of all block type combinations.")

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

    # =========================================================================
    # PRACTICE SESSION
    # =========================================================================
    print()
    header("Practice Session")
    info("Usually a single block type (e.g. volatile + precise) for task familiarization.")

    # 1. Volatility
    v_presets = stimgen.get("VOLATILITY_PRESETS", {})
    practice_vol = _pick_presets(
        "Add a block to practice",
        v_presets,
        "[mean, std, min, max] = epoch duration distribution (seconds)\n"
        "  mean  — average time before the laser jumps to a new position\n"
        "  std   — spread of the distribution\n"
        "  min   — shortest possible epoch\n"
        "  max   — longest possible epoch. Smaller values = faster jumps = more volatile.",
    )
    stimgen["PRACTICE_VOLATILITY"] = practice_vol

    # 2. Noise
    n_presets = stimgen.get("NOISE_PRESETS", {})
    practice_noise_mode = stimgen.get("PRACTICE_NOISE_MODE", "counterbalanced")
    practice_noise_mode_holder = [practice_noise_mode]
    practice_noise = _pick_presets(
        "Add a noise level to practice",
        n_presets,
        "Standard deviation (degrees) of observation noise added at each frame.\n"
        "Each noise × each volatility = one block type. Higher = more scattered.",
        multiply_by=practice_vol,
        noise_mode_holder=practice_noise_mode_holder,
    )
    practice_noise_mode = practice_noise_mode_holder[0]
    stimgen["PRACTICE_NOISE"] = practice_noise
    stimgen["PRACTICE_NOISE_MODE"] = practice_noise_mode

    from stimgen.laser.design_vola_stocha import get_block_count
    n_practice_types = get_block_count(practice_vol, practice_noise, practice_noise_mode)

    # Show block type summary
    print()
    _print_combinations_summary(practice_vol, practice_noise, v_presets, n_presets, practice_noise_mode)

    # 3. Block duration
    def _practice_dur_fmt(val_str: str) -> str:
        try:
            d = int(val_str)
            session_dur = n_practice_types * d
            return f"1 session = {n_practice_types} blocks × {d} min = {session_dur} min"
        except Exception:
            return ""

    stimgen["PRACTICE_BLOCK_DURATION_MIN"] = prompt_int(
        "Practice block duration (minutes per block)",
        stimgen.get("PRACTICE_BLOCK_DURATION_MIN", 1),
        min_val=1,
        hint_text="How long each block runs",
        live_formatter=_practice_dur_fmt,
    )

    # 4. Number of sessions
    pract_dur = stimgen["PRACTICE_BLOCK_DURATION_MIN"]

    def _practice_time_fmt(val_str: str) -> str:
        try:
            n = int(val_str)
            return f"generates {n} session file{'s' if n != 1 else ''}"
        except Exception:
            return ""

    stimgen["PRACTICE_N_SESSIONS"] = prompt_int(
        "Number of practice sessions",
        stimgen.get("PRACTICE_N_SESSIONS", 1),
        min_val=1, max_val=10,
        hint_text="Each session = one full set of block types",
        live_formatter=_practice_time_fmt,
    )

    practice_blocks = n_practice_types * stimgen["PRACTICE_N_SESSIONS"]
    practice_total = practice_blocks * pract_dur

    # =========================================================================
    # MAIN SESSION
    # =========================================================================
    print()
    header("Main Experiment Session")
    info("The main task. Usually the full 2×2 design (stable/volatile × precise/noisy).")

    # 1. Volatility
    main_vol = _pick_presets(
        "Add a block to main experiment",
        v_presets,
        "[mean, std, min, max] = epoch duration distribution (seconds)\n"
        "  mean  — average time before the laser jumps to a new position\n"
        "  std   — spread of the distribution\n"
        "  min   — shortest possible epoch\n"
        "  max   — longest possible epoch. Smaller values = faster jumps = more volatile.",
    )
    stimgen["MAIN_VOLATILITY"] = main_vol

    # 2. Noise
    main_noise_mode = stimgen.get("MAIN_NOISE_MODE", "counterbalanced")
    main_noise_mode_holder = [main_noise_mode]
    main_noise = _pick_presets(
        "Add a noise level to main experiment",
        n_presets,
        "Standard deviation (degrees) of observation noise added at each frame.\n"
        "Higher values = laser dot scatters more = harder to track.",
        multiply_by=main_vol,
        noise_mode_holder=main_noise_mode_holder,
    )
    main_noise_mode = main_noise_mode_holder[0]
    stimgen["MAIN_NOISE"] = main_noise
    stimgen["MAIN_NOISE_MODE"] = main_noise_mode

    from stimgen.laser.design_vola_stocha import get_block_count
    n_main_types = get_block_count(main_vol, main_noise, main_noise_mode)

    # Show block type summary
    print()
    _print_combinations_summary(main_vol, main_noise, v_presets, n_presets, main_noise_mode)

    # 3. Block duration
    def _main_dur_fmt(val_str: str) -> str:
        try:
            d = int(val_str)
            session_dur = n_main_types * d
            return f"1 session = {n_main_types} blocks × {d} min = {session_dur} min"
        except Exception:
            return ""

    stimgen["MAIN_BLOCK_DURATION_MIN"] = prompt_int(
        "Main block duration (minutes per block)",
        stimgen.get("MAIN_BLOCK_DURATION_MIN", 3),
        min_val=1,
        hint_text="How long each block runs",
        live_formatter=_main_dur_fmt,
    )

    # 4. Number of sessions
    main_dur = stimgen["MAIN_BLOCK_DURATION_MIN"]

    def _main_time_fmt(val_str: str) -> str:
        try:
            n = int(val_str)
            return f"generates {n} session file{'s' if n != 1 else ''}"
        except Exception:
            return ""

    stimgen["MAIN_N_SESSIONS"] = prompt_int(
        "Number of main sessions",
        stimgen.get("MAIN_N_SESSIONS", 3),
        min_val=1, max_val=20,
        hint_text="Each session = one full set of block types (one session CSV)",
        live_formatter=_main_time_fmt,
    )

    main_blocks = n_main_types * stimgen["MAIN_N_SESSIONS"]
    main_total = main_blocks * main_dur

    # =========================================================================
    # COMMON PARAMETERS
    # =========================================================================
    print()
    info(_c(C["bold"], "Common parameters (shared across all block types)"))
    print()

    stimgen["JUMP_DURATION_MIN_SEC"] = prompt_float(
        "  Min jump duration (s)",
        stimgen.get("JUMP_DURATION_MIN_SEC", 0.075),
        hint_text="Shortest time the true mean stays in one position before jumping",
        live_formatter=frames_live_formatter,
    )
    stimgen["JUMP_DURATION_MEAN_SEC"] = prompt_float(
        "  Mean jump duration (s)",
        stimgen.get("JUMP_DURATION_MEAN_SEC", 0.3),
        hint_text="Average time the true mean stays in one position",
        live_formatter=frames_live_formatter,
    )
    stimgen["JUMP_DURATION_MAX_SEC"] = prompt_float(
        "  Max jump duration (s)",
        stimgen.get("JUMP_DURATION_MAX_SEC", 1.0),
        hint_text="Longest time the true mean stays in one position before jumping",
        live_formatter=frames_live_formatter,
    )

    # Save custom presets back
    stimgen["VOLATILITY_PRESETS"] = v_presets
    stimgen["NOISE_PRESETS"] = n_presets

    # =========================================================================
    # DURATION SUMMARY
    # =========================================================================
    print()
    header("Experiment Duration")
    grand_total = practice_total + main_total

    print(_c(C["bold"], f"  Practice:  {practice_blocks} block{'s' if practice_blocks != 1 else ''} × {pract_dur} min  =  {practice_total} min"))
    print(_c(C["bold"], f"  Main:      {main_blocks} block{'s' if main_blocks != 1 else ''} × {main_dur} min  =  {main_total} min"))
    print(_c(C["dim"],   f"  {'─' * 45}"))
    print(_c(C["bold"], f"  Total:     {grand_total} min  ({grand_total / 60:.1f} h)"))
    print()

    n_main_sessions = stimgen["MAIN_N_SESSIONS"]
    n_practice_sessions = max(1, (practice_blocks + n_practice_types - 1) // n_practice_types)
    info(_c(C["dim"], f"  → {n_practice_sessions} practice session CSV{'s' if n_practice_sessions != 1 else ''}, {n_main_sessions} main session CSV{'s' if n_main_sessions != 1 else ''}"))

    # Auto-update dialog sessions/orders
    derived_sessions, derived_orders = _derive_sessions_and_orders()
    cfg["sessions"] = derived_sessions
    cfg["orders"] = derived_orders

    cfg["_stimgen_updates"] = stimgen
    return cfg


def configure_quick(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Quick setup — only the most commonly changed settings."""
    section("Quick Setup — Essential Settings")
    info("Only the most commonly changed settings. Use Advanced for full control.")

    # ── 2.2 & 2.3: Input keys ──
    print()
    info(_c(C["bold"], "Input Keys"))
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

    # ── 3.1: Trigger mode (+ serial / parallel settings if applicable) ──
    print()
    info(_c(C["bold"], "Trigger Setup"))
    mode = prompt(
        "Trigger mode",
        cfg.get("trigger_mode", "dummy"),
        choices=["dummy", "serial", "parallel", "lsl"],
        hint_text="'dummy' prints to console — use for testing without hardware",
    )
    cfg["trigger_mode"] = mode

    if mode == "serial":
        osdef = OS_DEFAULTS.get(cfg.get("target_os", "linux"), OS_DEFAULTS["linux"])
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
        osdef = OS_DEFAULTS.get(cfg.get("target_os", "linux"), OS_DEFAULTS["linux"])
        if osdef["parallel_addr"] is None:
            warn(f"Parallel ports are not supported on {cfg.get('target_os', 'linux')}.")
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

    # ── 4.1 & 4.2: Experiment design ──
    print()
    info(_c(C["bold"], "Experiment Design"))
    cfg["enable_practice"] = prompt_yn(
        "Include practice block?",
        cfg.get("enable_practice", True),
        hint_text="Shown before the main blocks; good for first-time participants",
    )
    cfg["show_earth_background"] = prompt_yn(
        "Show earth/world background behind the game?",
        cfg.get("show_earth_background", True),
        hint_text="If disabled, a plain black background is shown instead",
    )

    # ── 5.: All startup dialog options ──
    print()
    info(_c(C["bold"], "Startup Dialog Options"))

    available_fields = ["participant", "visit", "session", "order", "framing", "practice_mode"]
    current_fields = cfg.get("dialog_fields", ["participant", "visit", "session", "order", "framing"])

    cfg["dialog_fields"], action = prompt_multiselect(
        "Which fields should appear in the session dialog?",
        available_fields,
        defaults=current_fields,
    )
    if action == "b":
        raise GoBack()

    if "participant" not in cfg["dialog_fields"]:
        cfg["dialog_fields"] = ["participant"] + cfg["dialog_fields"]
        info("'participant' was force-included (required for data-file naming).")

    # ── sessions & orders: auto-derived from sequence generation config ──
    derived_sessions, derived_orders = _derive_sessions_and_orders()
    cfg["sessions"] = derived_sessions
    cfg["orders"] = derived_orders

    stimgen_snap = _read_stimgen_config()
    main_vol_quick = stimgen_snap.get("MAIN_VOLATILITY", ["stable", "volatile"])
    main_noise_quick = stimgen_snap.get("MAIN_NOISE", ["precise", "noisy"])
    main_types_quick = len(main_vol_quick) * len(main_noise_quick)
    main_n_sessions_quick = stimgen_snap.get("MAIN_N_SESSIONS", 3)

    print()
    info(_c(C["bold"], "Dropdown values (auto-detected from sequence generation config):"))
    info(f"  Sessions:  {', '.join(derived_sessions):20s} " + _c(C["dim"], f"({main_n_sessions_quick} session{'s' if main_n_sessions_quick != 1 else ''}, {main_types_quick} block types/session)"))
    info(f"  Orders:    {', '.join(derived_orders):20s} " + _c(C["dim"], "(all 4 counterbalancing orders always generated)"))

    cfg["visits"] = cfg.get("visits", ["1", "2"])
    cfg["framings"] = cfg.get("framings", ["loss", "win"])

    visible = [f for f in cfg["dialog_fields"] if f in ("visit", "session", "order", "framing")]
    if visible:
        info(f"  → Experimenter will choose from: {' × '.join(visible)} combinations")

    # ── 6.5: Currency symbol ──
    print()
    info(_c(C["bold"], "Currency"))
    cfg["currency_symbol"] = prompt(
        "Currency symbol",
        cfg.get("currency_symbol", "£"),
        hint_text="Displayed to the participant (Peduks Study: £)",
    )

    # ── 7.1: Audio (if yes, all other audio settings) ──
    print()
    info(_c(C["bold"], "Auditory MMN — Background Tones"))
    cfg["enable_audio"] = prompt_yn(
        "Enable background tones?",
        cfg.get("enable_audio", True),
        hint_text="Plays standard/deviant tones during the main blocks (Mismatch Negativity paradigm)",
    )
    if cfg["enable_audio"]:
        cfg["tone_freq_standard"] = prompt_float(
            "Standard tone frequency (Hz)",
            cfg.get("tone_freq_standard", 440.0),
            hint_text="Pitch of the frequent tone (Peduks Study: 440 Hz)",
        )
        cfg["tone_freq_deviant"] = prompt_float(
            "Deviant tone frequency (Hz)",
            cfg.get("tone_freq_deviant", 528.0),
            hint_text="Pitch of the rare tone (Peduks Study: 528 Hz)",
        )
        duration_ms = int(cfg.get("tone_duration", 0.07) * 1000)
        cfg["tone_duration"] = (
            prompt_int(
                "Base tone duration (ms)",
                duration_ms,
                min_val=10,
                max_val=500,
                hint_text="How long each tone plays by default (Peduks Study: 70 ms)",
            )
            / 1000.0
        )
        if prompt_yn("Customize standard vs. deviant durations separately?", False):
            std_dur_ms = int(cfg.get("tone_duration_standard", -1.0) * 1000)
            if std_dur_ms < 0:
                std_dur_ms = int(cfg["tone_duration"] * 1000)
            cfg["tone_duration_standard"] = (
                prompt_int(
                    "Standard tone duration (ms)",
                    std_dur_ms,
                    min_val=10,
                    max_val=500,
                )
                / 1000.0
            )
            dev_dur_ms = int(cfg.get("tone_duration_deviant", -1.0) * 1000)
            if dev_dur_ms < 0:
                dev_dur_ms = int(cfg["tone_duration"] * 1000)
            cfg["tone_duration_deviant"] = (
                prompt_int(
                    "Deviant tone duration (ms)",
                    dev_dur_ms,
                    min_val=10,
                    max_val=500,
                )
                / 1000.0
            )
        else:
            cfg["tone_duration_standard"] = -1.0
            cfg["tone_duration_deviant"] = -1.0

        cfg["tone_isi_frames"] = prompt_int(
            "Inter-stimulus interval (frames)",
            cfg.get("tone_isi_frames", 26),
            min_val=1,
            hint_text="Gap between tones in frames (Peduks Study: 26 frames)",
        )
        fps = cfg.get("target_refresh_rate", 60)
        info(f"  → Effective ISI: ~{cfg['tone_isi_frames'] / fps * 1000:.0f} ms at {fps} Hz")

        cfg["tone_volume"] = prompt_float(
            "Tone volume",
            cfg.get("tone_volume", 1.0),
            hint_text="0.0 = silent, 1.0 = full volume (Peduks Study: 1.0)",
        )
    else:
        info("Audio disabled — no tones will play.")

    # ── 8.: All sequence generation parameters ──
    cfg = configure_stimgen(cfg)

    return cfg


# ── summary table ───────────────────────────────────────────────────────────

def _kv(label: str, value: Any, suffix: str = "") -> str:
    s = str(value)
    label_text = f"{label}:"
    padded_label = label_text.ljust(20)
    return f"  {_c(C['dim'], padded_label)} {_c(C['bold'], s)}{suffix}"


def _format_volatility(v_list: List[str]) -> str:
    parts = []
    for v in v_list:
        if v == "stable":
            parts.append(_c(C["blue"], v))
        elif v == "volatile":
            parts.append(_c(C["red"], v))
        elif v == "medium":
            parts.append(_c(C["yellow"], v))
        else:
            parts.append(_c(C["green"], v))
    return ", ".join(parts)


def _format_noise(n_list: List[str]) -> str:
    parts = []
    for n in n_list:
        if n == "precise":
            parts.append(_c(C["blue"], n))
        elif n == "noisy":
            parts.append(_c(C["red"], n))
        else:
            parts.append(_c(C["green"], n))
    return ", ".join(parts)


def show_summary(cfg: Dict[str, Any], section_id: Optional[str] = None) -> None:
    if section_id is not None:
        section(f"Section {section_id} Summary")
    else:
        section("Configuration Summary")

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

    # Resolve values from new config structure
    prac_vol = stimgen_updates.get("PRACTICE_VOLATILITY", stimgen.get("PRACTICE_VOLATILITY", ["?"]))
    prac_noise = stimgen_updates.get("PRACTICE_NOISE", stimgen.get("PRACTICE_NOISE", ["?"]))
    prac_noise_mode = stimgen_updates.get("PRACTICE_NOISE_MODE", stimgen.get("PRACTICE_NOISE_MODE", "counterbalanced"))
    
    from stimgen.laser.design_vola_stocha import get_block_count
    try:
        prac_types = get_block_count(prac_vol, prac_noise, prac_noise_mode)
    except Exception:
        prac_types = len(prac_vol) * len(prac_noise)

    prac_sessions = stimgen_updates.get("PRACTICE_N_SESSIONS", stimgen.get("PRACTICE_N_SESSIONS", "?"))
    prac_dur = stimgen_updates.get("PRACTICE_BLOCK_DURATION_MIN", stimgen.get("PRACTICE_BLOCK_DURATION_MIN", "?"))
    
    main_vol = stimgen_updates.get("MAIN_VOLATILITY", stimgen.get("MAIN_VOLATILITY", ["?"]))
    main_noise = stimgen_updates.get("MAIN_NOISE", stimgen.get("MAIN_NOISE", ["?"]))
    main_noise_mode = stimgen_updates.get("MAIN_NOISE_MODE", stimgen.get("MAIN_NOISE_MODE", "counterbalanced"))
    
    try:
        main_types = get_block_count(main_vol, main_noise, main_noise_mode)
    except Exception:
        main_types = len(main_vol) * len(main_noise)

    main_sessions = stimgen_updates.get("MAIN_N_SESSIONS", stimgen.get("MAIN_N_SESSIONS", "?"))
    main_dur = stimgen_updates.get("MAIN_BLOCK_DURATION_MIN", stimgen.get("MAIN_BLOCK_DURATION_MIN", "?"))
    jump_min = stimgen_updates.get("JUMP_DURATION_MIN_SEC", stimgen.get("JUMP_DURATION_MIN_SEC", "?"))
    jump_mean = stimgen_updates.get("JUMP_DURATION_MEAN_SEC", stimgen.get("JUMP_DURATION_MEAN_SEC", "?"))
    jump_max = stimgen_updates.get("JUMP_DURATION_MAX_SEC", stimgen.get("JUMP_DURATION_MAX_SEC", "?"))

    try:
        prac_blocks = prac_types * int(prac_sessions)
        main_blocks = main_types * int(main_sessions)
        
        # Single session run duration (1 main session + practice if enabled)
        run_time = main_types * int(main_dur)
        if cfg.get("enable_practice", True):
            run_time += prac_types * int(prac_dur)
    except (ValueError, TypeError):
        prac_blocks = "?"
        main_blocks = "?"
        run_time = "?"

    shield_mode_str = "adjustable" if cfg.get("allow_shield_adjustment") else f"fixed ({cfg.get('fixed_shield_degrees', 20.0)}°)"

    prac_mode_hint = f" ({prac_noise_mode})" if len(prac_noise) >= 1 and len(set(prac_vol)) > 1 else ""
    main_mode_hint = f" ({main_noise_mode})" if len(main_noise) >= 1 and len(set(main_vol)) > 1 else ""

    items += [
        ("Practice", f"{_format_volatility(prac_vol)} × {_format_noise(prac_noise)}{prac_mode_hint} = {_c(C['bold'], str(prac_types))} type{'s' if prac_types != 1 else ''}", "7"),
        ("  Practice blocks", f"{_c(C['bold'], str(prac_blocks))} blocks ({prac_sessions} session{'s' if prac_sessions != 1 else ''} × {prac_types} types @ {prac_dur} min/block)", "7"),
        ("Main", f"{_format_volatility(main_vol)} × {_format_noise(main_noise)}{main_mode_hint} = {_c(C['bold'], str(main_types))} type{'s' if main_types != 1 else ''}", "7"),
        ("  Main blocks", f"{_c(C['bold'], str(main_blocks))} blocks ({main_sessions} session{'s' if main_sessions != 1 else ''} × {main_types} types @ {main_dur} min/block)", "7"),
        ("Run duration", f"{_c(C['bold'], str(run_time))} min" + (" (incl. practice)" if cfg.get("enable_practice", True) else "") if run_time != "?" else "?", "7"),
        ("Jump range", f"{jump_min}s - {jump_max}s (mean: {jump_mean}s)", "7"),
        ("Shield", f"{shield_mode_str}  ({cfg.get('rotation_speed', '?')}°/frame, r={cfg.get('circle_radius', '?')})", "5"),
        ("Loss factor", f"{cfg.get('loss_factor', '?')}  ({cfg.get('currency_symbol', '?')})", "5"),
        ("Min laser dur", f"{cfg.get('min_laser_duration_frames', '?')} frames", "5"),
    ]

    if cfg.get("enable_audio"):
        t_dur = cfg.get('tone_duration', 0.07)
        t_std = cfg.get('tone_duration_standard', -1.0)
        t_dev = cfg.get('tone_duration_deviant', -1.0)
        if t_std > 0 and t_dev > 0 and t_std != t_dev:
            dur_str = f"{t_std*1000:.0f}s/{t_dev*1000:.0f}d ms"
        else:
            dur_str = f"{t_dur*1000:.0f} ms"
        items += [
            ("Tones", f"{cfg.get('tone_freq_standard', '?')} / {cfg.get('tone_freq_deviant', '?')} Hz", "6"),
            ("Tone dur / ISI", f"{dur_str} / {cfg.get('tone_isi_frames', '?')} frames", "6"),
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

    max_visible = 0
    formatted_lines = []
    for label, value, _ in items:
        line = _kv(label, value)
        visible_len = len(re.sub(r'\033\[[0-9;]*m', '', line))
        formatted_lines.append((line, visible_len))
        if visible_len > max_visible:
            max_visible = visible_len

    width = max(59, max_visible + 4)
    print(_c(C["cyan"], f"  ┌{'─' * (width - 4)}┐"))
    for line, visible_len in formatted_lines:
        padding = max(0, (width - 4) - visible_len)
        print(_c(C["cyan"], "  │") + line + " " * padding + _c(C["cyan"], "│"))
    print(_c(C["cyan"], f"  └{'─' * (width - 4)}┘"))
    print()


def show_slim_summary(cfg: Dict[str, Any], mode: str = "generate") -> None:
    """Show only the values relevant to *mode* ('generate' or 'run')."""
    width = 59
    stimgen = _read_stimgen_config()
    stimgen_updates = cfg.get("_stimgen_updates") or {}

    # Resolve from new config structure
    prac_vol = stimgen_updates.get("PRACTICE_VOLATILITY", stimgen.get("PRACTICE_VOLATILITY", ["?"]))
    prac_noise = stimgen_updates.get("PRACTICE_NOISE", stimgen.get("PRACTICE_NOISE", ["?"]))
    prac_noise_mode = stimgen_updates.get("PRACTICE_NOISE_MODE", stimgen.get("PRACTICE_NOISE_MODE", "counterbalanced"))
    
    from stimgen.laser.design_vola_stocha import get_block_count
    try:
        prac_types = get_block_count(prac_vol, prac_noise, prac_noise_mode)
    except Exception:
        prac_types = len(prac_vol) * len(prac_noise)
        
    prac_sessions = stimgen_updates.get("PRACTICE_N_SESSIONS", stimgen.get("PRACTICE_N_SESSIONS", "?"))
    prac_dur = stimgen_updates.get("PRACTICE_BLOCK_DURATION_MIN", stimgen.get("PRACTICE_BLOCK_DURATION_MIN", "?"))
    
    main_vol = stimgen_updates.get("MAIN_VOLATILITY", stimgen.get("MAIN_VOLATILITY", ["?"]))
    main_noise = stimgen_updates.get("MAIN_NOISE", stimgen.get("MAIN_NOISE", ["?"]))
    main_noise_mode = stimgen_updates.get("MAIN_NOISE_MODE", stimgen.get("MAIN_NOISE_MODE", "counterbalanced"))
    
    try:
        main_types = get_block_count(main_vol, main_noise, main_noise_mode)
    except Exception:
        main_types = len(main_vol) * len(main_noise)
        
    main_sessions = stimgen_updates.get("MAIN_N_SESSIONS", stimgen.get("MAIN_N_SESSIONS", "?"))
    main_dur = stimgen_updates.get("MAIN_BLOCK_DURATION_MIN", stimgen.get("MAIN_BLOCK_DURATION_MIN", "?"))
    jump_min = stimgen_updates.get("JUMP_DURATION_MIN_SEC", stimgen.get("JUMP_DURATION_MIN_SEC", "?"))
    jump_mean = stimgen_updates.get("JUMP_DURATION_MEAN_SEC", stimgen.get("JUMP_DURATION_MEAN_SEC", "?"))
    jump_max = stimgen_updates.get("JUMP_DURATION_MAX_SEC", stimgen.get("JUMP_DURATION_MAX_SEC", "?"))

    try:
        prac_blocks = prac_types * int(prac_sessions)
        main_blocks = main_types * int(main_sessions)
        total_time = prac_blocks * int(prac_dur) + main_blocks * int(main_dur)
    except (ValueError, TypeError):
        prac_blocks = "?"
        main_blocks = "?"
        total_time = "?"

    visits = cfg.get("visits", ["?"])
    sessions = cfg.get("sessions", ["?"])
    orders = cfg.get("orders", ["?"])
    framings = cfg.get("framings", ["?"])
    n_combos = len(visits) * len(sessions) * len(orders) * len(framings)

    if mode == "generate":
        section("Sequence Generation — Key Parameters")

        prac_mode_hint = f" ({prac_noise_mode})" if len(prac_noise) >= 1 and len(set(prac_vol)) > 1 else ""
        main_mode_hint = f" ({main_noise_mode})" if len(main_noise) >= 1 and len(set(main_vol)) > 1 else ""

        items = [
            ("Practice", f"{_format_volatility(prac_vol)} × {_format_noise(prac_noise)}{prac_mode_hint} = {_c(C['bold'], str(prac_types))} type{'s' if prac_types != 1 else ''}"),
            ("  Practice blocks", f"{_c(C['bold'], str(prac_blocks))} blocks ({prac_sessions} session{'s' if prac_sessions != 1 else ''} @ {prac_dur} min)"),
            ("Main", f"{_format_volatility(main_vol)} × {_format_noise(main_noise)}{main_mode_hint} = {_c(C['bold'], str(main_types))} type{'s' if main_types != 1 else ''}"),
            ("  Main blocks", f"{_c(C['bold'], str(main_blocks))} blocks ({main_sessions} session{'s' if main_sessions != 1 else ''} @ {main_dur} min)"),
            ("Total time", f"{_c(C['bold'], str(total_time))} min" if total_time != "?" else "?"),
            ("Jump range", f"{jump_min}s – {jump_max}s (mean {jump_mean}s)"),
            ("Seq versions", f"main={SEQUENCE_VERSION}, practice={PRACTICE_SEQUENCE_VERSION}"),
            ("Practice files", f"{prac_sessions} session{'s' if prac_sessions != 1 else ''} × 4 orders = {prac_sessions * 4 if isinstance(prac_sessions, int) else '?'} CSVs"),
            ("Main files", f"{main_sessions} session{'s' if main_sessions != 1 else ''} × 4 orders = {main_sessions * 4 if isinstance(main_sessions, int) else '?'} CSVs"),
        ]

    elif mode == "run":
        section("Experiment Run — Key Parameters")

        fullscr = "fullscreen" if cfg.get("fullscreen") else f"{cfg.get('window_size_w', '?')}×{cfg.get('window_size_h', '?')}"
        display = f"{fullscr} on {cfg.get('monitor_name', '?')} @ {cfg.get('target_refresh_rate', '?')} Hz"
        input_info = f"{cfg.get('input_device', '?')} ({cfg.get('key_left', '?')} / {cfg.get('key_right', '?')})"

        trigger = cfg.get("trigger_mode", "?")
        if trigger == "serial":
            trigger = f"serial {cfg.get('serial_port', '?')} @ {cfg.get('serial_baud_rate', '?')}"
        elif trigger == "parallel":
            trigger = f"parallel {cfg.get('parallel_address', '?')}"
        elif trigger == "lsl":
            trigger = "LSL"
        else:
            trigger = "dummy (console)"

        if cfg.get("enable_audio"):
            t_dur = cfg.get('tone_duration', 0.07)
            t_std = cfg.get('tone_duration_standard', -1.0)
            t_dev = cfg.get('tone_duration_deviant', -1.0)
            if t_std > 0 and t_dev > 0 and t_std != t_dev:
                dur_str = f"{t_std*1000:.0f}s/{t_dev*1000:.0f}d ms"
            else:
                dur_str = f"{t_dur*1000:.0f} ms"
            audio = f"{cfg.get('tone_freq_standard', '?')}/{cfg.get('tone_freq_deviant', '?')} Hz, {dur_str}, vol {cfg.get('tone_volume', '?')}"
        else:
            audio = _c(C["dim"], "disabled")

        shield_mode_str = "adjustable" if cfg.get("allow_shield_adjustment") else f"fixed ({cfg.get('fixed_shield_degrees', 20.0)}°)"
        shield = f"{shield_mode_str}, {cfg.get('rotation_speed', '?')}°/frame, r={cfg.get('circle_radius', '?')}"

        items = [
            ("Display", display),
            ("Input", input_info),
            ("Triggers", trigger),
            ("Audio", audio),
            ("Practice", "Yes" if cfg.get("enable_practice") else "No"),
            ("Shield", shield),
            ("Currency", f"{cfg.get('currency_symbol', '?')} (loss factor {cfg.get('loss_factor', '?')})"),
            ("Combinations", f"{' × '.join(str(len(x)) for x in [visits, sessions, orders, framings])} = {n_combos}"),
        ]
    else:
        return

    max_visible = 0
    formatted_lines = []
    for label, value in items:
        line = _kv(label, value)
        visible_len = len(re.sub(r'\033\[[0-9;]*m', '', line))
        formatted_lines.append((line, visible_len))
        if visible_len > max_visible:
            max_visible = visible_len

    width = max(59, max_visible + 4)
    print(_c(C["cyan"], f"  ┌{'─' * (width - 4)}┐"))
    for line, visible_len in formatted_lines:
        padding = max(0, (width - 4) - visible_len)
        print(_c(C["cyan"], "  │") + line + " " * padding + _c(C["cyan"], "│"))
    print(_c(C["cyan"], f"  └{'─' * (width - 4)}┘"))
    print()


# ── pre-flight check ────────────────────────────────────────────────────────

def _preflight_check(cfg: Dict[str, Any]) -> List[str]:
    """Compare generated sequences against current config and check for issues.

    Returns a list of warning strings.  Empty list = everything OK.
    Checks:
      1. pkl metadata vs. stimgen config (block types, noise, durations, counts)
      2. min_laser_duration_frames vs. actual shortest laser runs in block CSVs
    """
    import csv
    import pickle
    from itertools import groupby

    warnings: List[str] = []
    seq_dir = PROJECT_ROOT / "sequences"
    stimgen = _read_stimgen_config()

    # ── 1. Check if sequences exist at all ──
    if not seq_dir.is_dir():
        warnings.append("No sequences/ directory found — generate sequences first.")
        return warnings

    practice_pkl = seq_dir / f"session_practice_{PRACTICE_SEQUENCE_VERSION}.pkl"
    main_pkl = seq_dir / f"session_main_{SEQUENCE_VERSION}.pkl"

    if not practice_pkl.exists() and not main_pkl.exists():
        warnings.append("No generated sequence .pkl files found — generate sequences first.")
        return warnings

    # ── 2. Compare pkl metadata against current stimgen config ──
    from stimgen.laser.design_vola_stocha import design_vola_stocha

    for pkl_path, label, vol_key, noise_key, mode_key, nsess_key, dur_key in [
        (practice_pkl, "Practice",
         "PRACTICE_VOLATILITY", "PRACTICE_NOISE", "PRACTICE_NOISE_MODE",
         "PRACTICE_N_SESSIONS", "PRACTICE_BLOCK_DURATION_MIN"),
        (main_pkl, "Main",
         "MAIN_VOLATILITY", "MAIN_NOISE", "MAIN_NOISE_MODE",
         "MAIN_N_SESSIONS", "MAIN_BLOCK_DURATION_MIN"),
    ]:
        if not pkl_path.exists():
            continue
        try:
            with open(pkl_path, "rb") as f:
                session = pickle.load(f)
        except Exception:
            warnings.append(f"{label}: Could not read {pkl_path.name}")
            continue

        # What the pkl contains
        pkl_block_types = session.get("blockTypes", [])
        pkl_n_blocks = session.get("nBlocks", 0)
        pkl_block_dur = session.get("blockDuration", 0)
        pkl_design_blocks = session.get("design", {}).get("blocks", [])

        # What the current config says
        cfg_vol = stimgen.get(vol_key, [])
        cfg_noise = stimgen.get(noise_key, [])
        cfg_mode = stimgen.get(mode_key, "counterbalanced")
        cfg_nsess = stimgen.get(nsess_key, 1)
        cfg_dur = stimgen.get(dur_key, 1)

        try:
            expected_design = design_vola_stocha(cfg_vol, cfg_noise, cfg_mode)
            expected_types = expected_design["blockTypes"]
            expected_blocks = expected_design["blocks"]
        except Exception:
            expected_types = []
            expected_blocks = []

        expected_n_blocks = len(expected_types) * cfg_nsess

        # Compare block types
        if sorted(pkl_block_types) != sorted(expected_types):
            warnings.append(
                f"{label} block types mismatch:\n"
                f"        Generated:  {', '.join(pkl_block_types)}\n"
                f"        Config:     {', '.join(expected_types)}"
            )

        # Compare block count
        if pkl_n_blocks != expected_n_blocks:
            warnings.append(
                f"{label} block count: generated {pkl_n_blocks}, "
                f"config expects {expected_n_blocks} "
                f"({len(expected_types)} types × {cfg_nsess} sessions)"
            )

        # Compare block duration
        if pkl_block_dur != cfg_dur:
            warnings.append(
                f"{label} block duration: generated {pkl_block_dur} min, "
                f"config expects {cfg_dur} min"
            )

        # Compare noise/volatility parameters per block type
        for i, (pkl_b, exp_b) in enumerate(zip(pkl_design_blocks, expected_blocks)):
            bt_name = pkl_block_types[i] if i < len(pkl_block_types) else f"block {i}"
            pkl_dur_params = pkl_b.get("durMeanStdMinMax", [])
            exp_dur_params = exp_b.get("durMeanStdMinMax", [])
            pkl_noise_val = pkl_b.get("noiseStd", None)
            exp_noise_val = exp_b.get("noiseStd", None)

            if pkl_dur_params != exp_dur_params:
                warnings.append(
                    f"{label} '{bt_name}' epoch params: "
                    f"generated {pkl_dur_params}, config {exp_dur_params}"
                )
            if pkl_noise_val != exp_noise_val:
                warnings.append(
                    f"{label} '{bt_name}' noise: "
                    f"generated {pkl_noise_val}°, config {exp_noise_val}°"
                )

    # ── 3. Check min_laser_duration vs block CSV run lengths ──
    min_laser_on = cfg.get("min_laser_duration_frames", 6)
    laser_warn_blocks: List[Tuple[str, int]] = []

    block_csvs = sorted(seq_dir.glob("*_block*.csv"))
    for csv_path in block_csvs:
        try:
            positions = []
            with open(csv_path, "r") as fh:
                reader = csv.reader(fh)
                next(reader)  # skip header
                for row in reader:
                    positions.append(float(row[1]))

            # Find shortest run of consecutive identical positions
            runs = []
            for _, group in groupby(positions):
                runs.append(sum(1 for _ in group))
            if runs:
                shortest = min(runs)
                if shortest <= min_laser_on:
                    name = csv_path.stem  # e.g. "main_v4_block3"
                    laser_warn_blocks.append((name, shortest))
        except Exception:
            pass

    if laser_warn_blocks:
        block_details = ", ".join(f"{name} ({n}f)" for name, n in laser_warn_blocks[:5])
        extra = f" (+{len(laser_warn_blocks) - 5} more)" if len(laser_warn_blocks) > 5 else ""
        warnings.append(
            f"Laser visibility: {len(laser_warn_blocks)} block(s) have runs ≤ "
            f"min_laser_duration_frames ({min_laser_on}):\n"
            f"        {block_details}{extra}\n"
            f"        The laser won't be hidden during these short runs."
        )

    return warnings


def _show_preflight_warnings(
    cfg: Dict[str, Any], warnings: List[str]
) -> bool:
    """Display preflight warnings and offer to regenerate.

    Returns True if the experiment should proceed, False to abort back to menu.
    """
    section("Pre-flight Check")

    if not warnings:
        print(_c(C["green"], "  ✓ All checks passed — sequences match current config."))
        print()
        return True

    # Show warnings
    print(_c(C["yellow"], f"  ⚠ {len(warnings)} issue{'s' if len(warnings) != 1 else ''} detected:"))
    print()
    for i, w in enumerate(warnings, 1):
        lines = w.split("\n")
        print(f"    {_c(C['yellow'], str(i) + '.')} {lines[0]}")
        for extra_line in lines[1:]:
            print(f"       {_c(C['dim'], extra_line)}")
    print()

    # Offer choices
    print(f"    {_c(C['cyan'], 'g')} = Regenerate sequences with current config, then run")
    print(f"    {_c(C['cyan'], 'r')} = Run anyway (ignore warnings)")
    print(f"    {_c(C['dim'], 'b')} = Go back to menu")
    print()

    while True:
        choice = input(_c(C["magenta"], "  ❯ ")).strip().lower()
        if choice == "b":
            return False
        elif choice == "r":
            return True
        elif choice == "g":
            if run_sequence_generation(cfg.copy()):
                return True
            else:
                fail("Sequence generation failed.")
                return False
        else:
            warn("Choose 'g', 'r', or 'b'.")


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
    # ── per-task-type summary ──
    seq_dir = PROJECT_ROOT / "sequences"
    print()
    info(_c(C["bold"], "Generated session CSV files:"))
    task_types = [
        ("practice", "Practice"),
        ("main", "Main experiment"),
    ]
    for prefix, label in task_types:
        dirs = sorted([d for d in seq_dir.iterdir() if d.is_dir() and d.name.startswith(f"coin_{prefix}_")])
        if not dirs:
            continue
        session_counts = [len(list(d.glob("session_*.csv"))) for d in dirs]
        total_csvs = sum(session_counts)
        info(f"  {label:20s} {total_csvs} CSVs across {len(dirs)} orders ({', '.join(str(c) for c in session_counts)} sessions/order)")

    csv_count = len(list(seq_dir.glob("*.csv"))) if seq_dir.is_dir() else 0
    order_count = len([d for d in seq_dir.iterdir() if d.is_dir() and d.name.startswith("coin_")]) if seq_dir.is_dir() else 0
    print()
    success(f"Laser sequences written ({csv_count} block CSVs, {order_count} order dirs)")

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

    # ── auto-sync dialog dropdowns with generated files ──
    derived_sessions, derived_orders = _derive_sessions_and_orders()
    cfg["sessions"] = derived_sessions
    cfg["orders"] = derived_orders
    _write_laser_task_config(cfg)
    info(f"Dialog sessions auto-synced: {', '.join(derived_sessions)}  |  orders: {', '.join(derived_orders)}")

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
        "SAMPLE_RATE",
        "JUMP_DURATION_MEAN_SEC", "JUMP_DURATION_MIN_SEC", "JUMP_DURATION_MAX_SEC",
    ]:
        if key in stimgen:
            print(_kv(key, stimgen[key]))

    # Practice
    prac_vol = stimgen.get("PRACTICE_VOLATILITY", [])
    prac_noise = stimgen.get("PRACTICE_NOISE", [])
    print(_kv("Practice volatility", ", ".join(prac_vol)))
    print(_kv("Practice noise", ", ".join(prac_noise)))
    print(_kv("Practice sessions", stimgen.get("PRACTICE_N_SESSIONS", "?")))
    print(_kv("Practice block dur", f"{stimgen.get('PRACTICE_BLOCK_DURATION_MIN', '?')} min"))

    # Main
    main_vol = stimgen.get("MAIN_VOLATILITY", [])
    main_noise = stimgen.get("MAIN_NOISE", [])
    print(_kv("Main volatility", ", ".join(main_vol)))
    print(_kv("Main noise", ", ".join(main_noise)))
    print(_kv("Main sessions", stimgen.get("MAIN_N_SESSIONS", "?")))
    print(_kv("Main block dur", f"{stimgen.get('MAIN_BLOCK_DURATION_MIN', '?')} min"))

    # Presets
    vp = stimgen.get("VOLATILITY_PRESETS", {})
    np_ = stimgen.get("NOISE_PRESETS", {})
    print(_kv("Volatility presets", ", ".join(vp.keys()) if vp else "none"))
    print(_kv("Noise presets", ", ".join(np_.keys()) if np_ else "none"))
    sd = stimgen.get("SAVED_DESIGNS", {})
    if sd:
        print(_kv("Saved designs", ", ".join(sd.keys())))

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
    ("4", "Experiment design (practice, earth bg, reward reset)", configure_design),
    ("5", "Shield mechanics & reward (size, speed, loss factor)", configure_shield_reward),
    ("6", "Auditory MMN (tone frequencies, duration, ISI)", configure_audio),
    ("7", "Sequence generation (noise levels, volatility, durations)", configure_stimgen),
    ("8", "Startup dialog (which fields, dropdown options, framing)", configure_dialog),
]

SECTION_MAP: Dict[str, Tuple[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = {
    slug: (desc, fn) for slug, desc, fn in SECTION_REGISTRY
}


def _run_advanced_menu(cfg: Dict[str, Any]) -> bool:
    """Advanced section-by-section menu.  Returns True if config was modified."""
    dirty = False

    def _quick_setup():
        """Run all sections sequentially with current defaults."""
        nonlocal cfg, dirty
        for slug, desc, fn in SECTION_REGISTRY:
            print()
            info(_c(C["bold"], f"Running section {slug}: {desc}"))
            try:
                cfg = fn(cfg)
            except GoBack:
                info("Quick setup cancelled — returning to menu.")
                return
            dirty = True
        show_summary(cfg)
        if prompt_yn("Save all sections?", True):
            _write_laser_task_config(cfg)
            _save_stimgen_from_cfg(cfg.copy())
            dirty = False
            success("All sections saved.")
        else:
            info("Changes held in memory — use 's' to review, 'b' to go back.")

    while True:
        clear()
        header("CoIn Laser Task — Advanced Settings")

        if dirty:
            print(_c(C["yellow"], "  ← unsaved changes in memory"))
            print()

        print("  Sections to configure:\n")
        for slug, desc, _ in SECTION_REGISTRY:
            print(f"    {_c(C['green'], slug)})  {desc}")

        print()
        print(f"  {_c(C['cyan'], 'a')})  Run all sections")
        print(f"  {_c(C['cyan'], 's')})  Show current configuration")
        print(f"  {_c(C['cyan'], 'g')})  Generate sequences")
        print(f"  {_c(C['cyan'], 'r')})  Run experiment" + _c(C["dim"], "  (python main.py)"))
        print(f"  {_c(C['dim'], 'b')})  Back to main menu")

        print()
        choice = input(_c(C["magenta"], "  ❯ ")).strip().lower()

        if choice == "b":
            return dirty
        elif choice == "a":
            try:
                _quick_setup()
            except GoBack:
                info("All-sections cancelled — returning to menu.")
        elif choice == "s":
            show_summary(cfg)
        elif choice == "r":
            show_slim_summary(cfg, "run")
            if dirty:
                warn("Unsaved config changes — run anyway?")
                if not prompt_yn("Proceed without saving?", True):
                    continue
            # Pre-flight: compare generated sequences against current config
            pf_warnings = _preflight_check(cfg)
            if not _show_preflight_warnings(cfg, pf_warnings):
                continue
            print()
            info("Launching experiment …")
            print()
            subprocess.run([sys.executable, str(PROJECT_ROOT / "main.py")])
            return dirty
        elif choice == "g":
            show_slim_summary(cfg, "generate")
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
                        pf_warnings = _preflight_check(cfg)
                        if _show_preflight_warnings(cfg, pf_warnings):
                            print()
                            info("Launching experiment …")
                            print()
                            subprocess.run([sys.executable, str(PROJECT_ROOT / "main.py")])
                            return dirty
        elif choice in SECTION_MAP:
            desc, fn = SECTION_MAP[choice]
            try:
                cfg = fn(cfg)
            except GoBack:
                info("Returned to section menu.")
                continue
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

        if choice not in ("b", "q"):
            print()
            input(_c(C["dim"], "  Press Enter to continue …"))


def run_section_menu(cfg: Dict[str, Any]) -> None:
    """Top-level menu — Quick Setup vs. Advanced Settings."""
    dirty = False

    while True:
        clear()
        header("CoIn Laser Task — Setup")

        if dirty:
            print(_c(C["yellow"], "  ← unsaved changes in memory"))
            print()

        print("  Setup mode:\n")
        print(f"    {_c(C['green'], '1')})  Quick Setup — essential settings only")
        print(f"    {_c(C['green'], '2')})  Advanced Settings — all sections")
        print()
        print(f"  {_c(C['cyan'], 's')})  Show current configuration")
        print(f"  {_c(C['cyan'], 'g')})  Generate sequences")
        print(f"  {_c(C['cyan'], 'r')})  Run experiment" + _c(C["dim"], "  (python main.py)"))
        print(f"  {_c(C['dim'], 'q')})  Quit & save")

        print()
        choice = input(_c(C["magenta"], "  ❯ ")).strip().lower()

        if choice == "q":
            if dirty:
                if prompt_yn("Save changes before quitting?", True):
                    _write_laser_task_config(cfg)
                    _save_stimgen_from_cfg(cfg.copy())
                    success("Config saved.")
            break
        elif choice == "1":
            try:
                cfg = configure_quick(cfg)
            except GoBack:
                info("Quick setup cancelled.")
                continue
            dirty = True
            show_summary(cfg)
            if prompt_yn("Save quick settings?", True):
                _write_laser_task_config(cfg)
                _save_stimgen_from_cfg(cfg.copy())
                dirty = False
                success("Quick settings saved.")
            else:
                info("Changes held in memory — use 's' to review, 'q' to save & quit.")
        elif choice == "2":
            if _run_advanced_menu(cfg):
                dirty = True
        elif choice == "s":
            show_summary(cfg)
        elif choice == "r":
            show_slim_summary(cfg, "run")
            if dirty:
                warn("Unsaved config changes — run anyway?")
                if not prompt_yn("Proceed without saving?", True):
                    continue
            # Pre-flight: compare generated sequences against current config
            pf_warnings = _preflight_check(cfg)
            if not _show_preflight_warnings(cfg, pf_warnings):
                continue
            print()
            info("Launching experiment …")
            print()
            subprocess.run([sys.executable, str(PROJECT_ROOT / "main.py")])
            return
        elif choice == "g":
            show_slim_summary(cfg, "generate")
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
                        pf_warnings = _preflight_check(cfg)
                        if _show_preflight_warnings(cfg, pf_warnings):
                            print()
                            info("Launching experiment …")
                            print()
                            subprocess.run([sys.executable, str(PROJECT_ROOT / "main.py")])
                            return
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
