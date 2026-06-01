# StimulusStyle, ExperimentConfig, TRIGGER_CODES
import sys
from dataclasses import dataclass, field
from typing import List, Tuple, Dict

from config_shared import SEQUENCE_VERSION, PRACTICE_SEQUENCE_VERSION, SEQUENCE_ROOT
from laserTask.shield import ShieldSizeConfig
#from laserTask.instructions import InstructionSet

@dataclass
class StimulusStyle:
    """Visual appearance settings for all on-screen elements.

    This is the one configuration class that is still edited directly in
    Python rather than via ``config.json``.  Change values here to adjust
    colours, sizes, positions, and fonts without touching experiment logic.

    Notes
    -----
    Colour values use PsychoPy's ``rgb`` colour space where each channel
    ranges from -1 (black / off) to +1 (full intensity).
    """

    # -- General layout --
    center_pos: Tuple[float, float] = (0.0, -0.025)
    """Centre of the game area (source icon, shield origin)."""

    font: str = "Arial"
    text_color: str = "white"
    text_size: float = 0.05
    title_size: float = 0.1
    small_text_size: float = 0.04

    # -- Shield --
    shield_fill_color: List[float] = field(
        default_factory=lambda: [1.0, 1.0, 1.0]
    )
    shield_hit_color: List[float] = field(
        default_factory=lambda: [1.0, 0.0, 0.0]
    )
    """Colour the shield turns when it absorbs the laser (i.e., a hit)."""
    shield_line_color: List[float] = field(
        default_factory=lambda: [0.0, 0.0, 0.0]
    )
    shield_size_outer: Tuple[float, float] = (0.053, 0.053)
    shield_size_inner: Tuple[float, float] = (0.048, 0.048)

    # -- Shield centre line --
    centre_line_color: str = "blue"
    centre_line_width: float = 3.0

    # -- Laser beam --
    laser_color: str = "red"
    laser_line_width: float = 10.0
    laser_radius_factor: float = 1.1
    """Multiplied by circle_radius to set the short laser length."""
    laser_long_radius_factor: float = 1.4
    """Multiplied by circle_radius to set the extended laser length."""

    # -- Background circle (harmless area) --
    harmless_area_size: Tuple[float, float] = (0.32, 0.32)
    harmless_area_color: List[float] = field(
        default_factory=lambda: [0.0, 0.0, 0.0]
    )

    # -- Radioactive-source icon --
    source_size: Tuple[float, float] = (0.1, 0.1)

    # -- Reward bar --
    reward_bar_color: str = "blue"
    reward_bar_x: float = 0.6
    reward_bar_width: float = 0.05
    reward_loss_color: List[float] = field(
        default_factory=lambda: [1.0, -1.0, -1.0]
    )
    reward_gain_color: List[float] = field(
        default_factory=lambda: [-1.0, 1.0, -1.0]
    )

    # -- Progress bar --
    progress_bar_color: str = "green"
    progress_bar_edge_color: str = "green"
    # wedge_resolution: int = 720
    # progress_bar_color: Tuple[float, float, float]= (0, 1, 0)
    # progress_bar_edge_color: Tuple[float, float, float] = (0, 1, 0)
    progress_bar_y: float = -0.45
    progress_bar_height: float = 0.05
    progress_bar_width: float = 0.8
    #progress_circle_size: Tuple[float, float] = (0.015, 0.015)
    progress_circle_size: Tuple[float, float] = (0.12, 0.12)
    progress_circle_width: float = 23.5

@dataclass
class ExperimentConfig:
    """Schema and defaults for the experiment configuration.

    Runtime values are loaded from ``laserTask/config.json`` (generated
    by ``python setup.py``).  Edit that file — or run the setup wizard —
    rather than modifying defaults here directly.
    """

    # -- File paths (relative to script directory) --
    # Values sourced from config_shared.py — change them there.
    sequence_version: str = SEQUENCE_VERSION
    practice_sequence_version: str = PRACTICE_SEQUENCE_VERSION
    sequence_root: str = SEQUENCE_ROOT
    data_root: str = "data/"
    image_root: str = "images/"

    # -- Display --
    target_os: str = "linux"
    window_size: Tuple[int, int] = (1512, 982)
    fullscreen: bool = True
    screen_index: int = 0
    monitor_name: str = "testMonitor"
    background_color: List[float] = field(
        default_factory=lambda: [0.0, 0.0, 0.0]
    )
    target_refresh_rate: int = 60
    """Fallback refresh rate (Hz) if auto-detection fails."""

    # -- Keyboard controls --
    key_right: str = "j"
    key_left: str = "f"
    key_next: str = "space"
    # controls instruction screen -- other option is "response_box"
    # if set to response_box, instruction do not name the keys
    # NOTE: must still set key mappings to code the device sends! 
    input_device: str = "keyboard"

    # -- Dialog configuration --
    dialog_fields: list = field(default_factory=lambda: ["participant", "visit", "session", "order", "framing", "practice_mode"])
    """Fields shown in the session setup dialog.

    Must be a subset of ``["participant", "visit", "session", "order",
    "framing", "practice_mode"]``.  ``"participant"`` is always force-included even if
    omitted (required for data-file naming).

    Example — run without framings::

        dialog_fields = ["participant", "visit", "session", "order"]
    """

    # -- Experiment structure --
    visits: list = field(default_factory=lambda: ["1", "2"])
    sessions: list = field(default_factory=lambda: ["1"])
    orders: list = field(default_factory=lambda: ["1", "2", "3", "4"])
    framings: list = field(default_factory=lambda: ["loss", "win"])
    """Dropdown options for the session dialog (if enabled via dialog_fields)."""

    # -- Keyboard backend --
    keyboard_backend: str = ""
    """PsychoPy keyboard backend.

    Options: ``"ptb"`` (Psychtoolbox), ``"event"`` (pyglet events),
    ``"iohub"`` (ioHub, cross-platform).

    Default is ``""`` (auto-selects ``"ptb"`` on Windows, ``"iohub"`` on
    Linux / macOS).
    """
    

    # -- Shield mechanics --
    # TODO: move circle_radius and rotation_speed to ShieldSizeConfigs?
    rotation_speed: float = 1.0
    """Shield rotation speed in degrees per frame."""
    circle_radius: float = 3.0
    """Radius of the game circle (PsychoPy height units)."""
    allow_shield_adjustment: bool = False
    """Whether to allow growing/shrinking the shield size during the game."""
    fixed_shield_degrees: float = 20.0
    """Fixed angular half-width of the shield in degrees (only used if allow_shield_adjustment is False)."""
    shield_sizes: ShieldSizeConfig = field(
        default_factory=ShieldSizeConfig.peduks_fixed
    )

    use_legacy_key_tracking: bool = True
    """Set to True to restore the original/legacy key tracking behavior."""


    # -- Reward --
    loss_factor: float = 0.003
    currency_symbol: str = "€"

    flash_feedback: bool = False

    # -- Trigger settings --
    trigger_mode: str = "parallel"
    """How event markers are sent to the recording system.

    Options
    -------
    ``"dummy"``    – Print to console (no hardware required).
    ``"serial"``   – Write to a serial port (e.g. BrainVision TriggerBox).
    ``"parallel"`` – Write to a parallel/LPT port.
    ``"lsl"``      – Push via Lab Streaming Layer.
    """
    serial_port: str = "/dev/ttyUSB0"
    """Serial port for trigger output.  Leave empty for OS-appropriate default
    (Linux: /dev/ttyUSB0, Windows: COM6, macOS: /dev/cu.usbserial-*)."""
    serial_baud_rate: int = 115200
    serial_timeout: float = 0.001
    parallel_address: str = "/dev/parport0"
    """Parallel port address.  Leave empty for OS-appropriate default
    (Linux: /dev/parport0, Windows: 0x0378, macOS: unsupported)."""

    # -- Auditory stimulation --
    enable_audio: bool = True
    """Set to ``False`` to run the task without any background tones."""
    mmn_type: str = "duration"
    """Mismatch negativity paradigm type.

    ``"frequency"`` — standard and deviant differ in pitch
    (e.g. 440 Hz vs 528 Hz).  ``"duration"`` — standard and
    deviant differ in length (e.g. 50 ms vs 100 ms) but share
    the same pitch.
    """
    tone_freq_standard: float = 440.0
    tone_freq_deviant: float = 440.0
    tone_duration: float = 0.05
    """Duration of each tone (seconds)."""
    tone_duration_standard: float = 0.05
    """Duration of standard tones (seconds). If negative, falls back to tone_duration."""
    tone_duration_deviant: float = 0.1
    """Duration of deviant tones (seconds). If negative, falls back to tone_duration."""
    tone_volume: float = 1.0
    tone_isi_frames: int = 24
    """Inter-stimulus interval between successive tones (in frames).
    
    PEDUKS MMN default: 26 frames = ~433 ms at 60 Hz (matches MATLAB's 430 ms).
    """

    # -- Visual style --
    show_earth_background: bool = True
    """Whether to show the earth/world picture as the background during main trials. 
    As of right now it is always visible during practice trials."""
    show_rbar: bool = True
    show_source: bool = True
    round_pbar: bool = False
    style: StimulusStyle = field(default_factory=StimulusStyle)
    #instruction_set: InstructionSet = InstructionSet.COGPSY

    # -- Session structure --
    enable_practice: bool = True
    """Whether to run the practice session before the main experiment."""

    reset_reward_after_practice: bool = True
    """Reset session reward to 0 after practice ends."""

    n_blocks: int = 1
    min_laser_duration_frames: int = 6
    """Hardcoded maximum frames the laser should be visible before disappearing."""

    # validate device settings
    def __post_init__(self):
        valid_devices = {"keyboard", "response_box"}
        if self.input_device not in valid_devices:
            raise ValueError(
                f"input_device '{self.input_device}' not recognised. "
                f"Choose from: {valid_devices}"
            )
        # Auto-select OS-appropriate defaults if not explicitly set
        if not self.keyboard_backend:
            self.keyboard_backend = "ptb" if sys.platform == "win32" else "iohub"

        # Validate that the selected backend is actually available.
        # PTB requires the `psychtoolbox` package; if it is missing,
        # PsychoPy silently falls back to `event` with only a log
        # message — easy to miss in an experiment context.
        if self.keyboard_backend == "ptb":
            try:
                import psychtoolbox  # noqa: F401
            except ImportError:
                import warnings
                warnings.warn(
                    "keyboard_backend='ptb' selected but `psychtoolbox` is not "
                    "installed. Falling back to 'iohub'. Install with: "
                    "pip install psychtoolbox",
                    stacklevel=2,
                )
                self.keyboard_backend = "iohub"

        # ioHub needs the iohub server, which PsychoPy launches on demand,
        # but the package must be present. If somehow stripped from a
        # minimal install, fall back to the always-available `event`.
        if self.keyboard_backend == "iohub":
            try:
                from psychopy.iohub import launchHubServer  # noqa: F401
            except ImportError:
                import warnings
                warnings.warn(
                    "keyboard_backend='iohub' selected but `psychopy.iohub` is "
                    "not available. Falling back to 'event'.",
                    stacklevel=2,
                )
                self.keyboard_backend = "event"
        if not self.serial_port:
            if sys.platform == "win32":
                self.serial_port = "COM6"
            elif sys.platform == "darwin":
                self.serial_port = "/dev/cu.usbserial-*"
            else:
                self.serial_port = "/dev/ttyUSB0"
        if not self.parallel_address:
            if sys.platform == "win32":
                self.parallel_address = "0x0378"
            elif sys.platform == "darwin":
                self.parallel_address = ""  # macOS has no parallel port
            else:
                self.parallel_address = "/dev/parport0"

        # Rebuild shield_sizes from primary config fields so that changes
        # to loss_factor, fixed_shield_degrees, and flash_feedback are
        # reflected in the shield cost/colour calculations.
        if self.allow_shield_adjustment:
            self.shield_sizes = ShieldSizeConfig.adjustable_standard(
                loss_factor=self.loss_factor,
                flash_feedback=self.flash_feedback,
            )
        else:
            self.shield_sizes = ShieldSizeConfig.fixed_custom(
                degrees=self.fixed_shield_degrees,
                loss_factor=self.loss_factor,
                flash_feedback=self.flash_feedback,
            )

        # Fall back to tone_duration if specific durations aren't set
        if self.tone_duration_standard < 0:
            self.tone_duration_standard = self.tone_duration
        if self.tone_duration_deviant < 0:
            self.tone_duration_deviant = self.tone_duration


# Trigger event codes — used both for sending and for data logging.
TRIGGER_CODES: Dict[str, int] = {
    "exp_start":   100,
    "exp_end":     101,
    "block_start":  80,
    "block_end":    90,
    "last_frame":   99,
    "laser_hit":    10,
    "laser_miss":   20,
    "key_right":    30,
    "key_left":     40,
    "key_release":  50,
    "shield_shrink": 60,
    "shield_grow": 70,
    "tone_standard": 1,
    "tone_deviant":  2,
}


# ------------------------------------------------------------------ #
#  CONFIG LOADING                                                     #
# ------------------------------------------------------------------ #
# The ExperimentConfig dataclass above defines the schema (field names,
# types, documentation, and validation logic).  The actual runtime
# values live in *config.json* (generated by ``python setup.py``).
#
# ── How to configure ───────────────────────────────────────────────
#   • python setup.py          interactive wizard (recommended)
#   • Edit laserTask/config.json directly, then re-run setup.py
#
# ── What happens on first run ──────────────────────────────────────
#   If config.json doesn't exist, get_config() returns the dataclass
#   defaults above.  Run setup.py once to generate config.json.
#
# ── Derived fields ─────────────────────────────────────────────────
#   shield_sizes, keyboard_backend, serial_port, and tone duration
#   fallbacks are computed by __post_init__ at load time.  They are
#   NOT stored in config.json — only the *primary* fields that
#   control them are stored.
# ------------------------------------------------------------------ #

import json as _json
from pathlib import Path as _Path

# Fields whose JSON array value should be converted to a tuple.
_TUPLE_FIELDS = {"window_size"}


def _load_config_json() -> dict:
    """Load laserTask/config.json, returning {} if it doesn't exist."""
    cfg_path = _Path(__file__).parent / "config.json"
    if not cfg_path.is_file():
        return {}
    return _json.loads(cfg_path.read_text(encoding="utf-8"))


def get_config() -> ExperimentConfig:
    """Create a fully-initialised ExperimentConfig from config.json.

    Fields present in config.json override the dataclass defaults.
    Fields NOT in config.json keep their dataclass default.
    ``__post_init__`` is always called to compute derived values
    (shield_sizes, keyboard_backend, tone fallbacks, etc.).

    If config.json doesn't exist (first run), all dataclass defaults
    are used — the experiment will run with sensible starter values.
    """
    cfg = ExperimentConfig()
    data = _load_config_json()

    for key, value in data.items():
        # Convert JSON lists back to tuples for known tuple fields.
        if key in _TUPLE_FIELDS and isinstance(value, list):
            value = tuple(value)
        # Only set fields that exist on the dataclass (skip unknown keys).
        if key in ExperimentConfig.__dataclass_fields__:
            setattr(cfg, key, value)

    # Always recompute derived fields from the loaded primary fields.
    cfg.__post_init__()
    return cfg


def get_preset_origin() -> dict | None:
    """Return preset origin info, or None if no preset was loaded."""
    origin_path = _Path(__file__).parent / ".preset_origin.json"
    if not origin_path.is_file():
        return None
    return _json.loads(origin_path.read_text(encoding="utf-8"))
