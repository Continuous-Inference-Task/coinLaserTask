# StimulusStyle, ExperimentConfig, TRIGGER_CODES
import sys
from dataclasses import dataclass, field
from typing import List, Tuple, Dict

from config_shared import SEQUENCE_VERSION, PRACTICE_SEQUENCE_VERSION, SEQUENCE_ROOT
from laserTask.shield import ShieldSizeConfig

@dataclass
class StimulusStyle:
    """All visual-appearance settings in one place.

    Edit values here to change colours, sizes, positions, and fonts of
    every visual element — no need to search through experiment logic.

    Notes
    -----
    Colour values use PsychoPy's ``rgb`` colour space where each channel
    ranges from -1 (black) to +1 (full intensity).
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
    progress_bar_y: float = -0.45
    progress_bar_height: float = 0.05
    progress_bar_width: float = 0.8


@dataclass
class ExperimentConfig:
    """Central, single-source-of-truth configuration for the experiment.

    Modify values here to adapt the experiment to a new setup without
    touching any experiment-logic code below.
    """

    # -- File paths (relative to script directory) --
    # Values sourced from config_shared.py — change them there.
    sequence_version: str = SEQUENCE_VERSION
    practice_sequence_version: str = PRACTICE_SEQUENCE_VERSION
    sequence_root: str = SEQUENCE_ROOT
    data_root: str = "data/"
    image_root: str = "images/"

    # -- Display --
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
    # controls instruction screen -- other option is "response_box"
    # if set to response_box, instruction do not name the keys
    # NOTE: must still set key mappings to code the device sends! 
    input_device: str = "keyboard" 

    # -- Experiment structure --
    visits: list = field(default_factory=lambda: ["1", "2"])
    sessions: list = field(default_factory=lambda: ["1", "2"])
    orders: list = field(default_factory=lambda: ["1", "2"])
    framings: list = field(default_factory=lambda: ["loss", "win"])
    """Framing options shown in the startup dialog dropdown."""

    # -- Keyboard backend --
    keyboard_backend: str = ""
    """PsychoPy keyboard backend.

    Options: ``"ptb"`` (Psychtoolbox, best precision, requires elevated
    privileges on Linux), ``"event"`` (pyglet events, works everywhere),
    ``"iohub"`` (ioHub, cross-platform).

    Leave empty for OS-appropriate auto-selection:
    Windows → ``"ptb"``,  Linux / macOS → ``"event"``.
    """
    

    # -- Shield mechanics --
    # TODO: move circle_radius and rotation_speed to ShieldSizeConfigs?
    rotation_speed: float = 1.0
    """Shield rotation speed in degrees per frame."""
    circle_radius: float = 3.0
    """Radius of the game circle (PsychoPy height units)."""
    allow_shield_adjustment: bool = False # If True, participant can resize shield with key_shrink/key_grow.
    """Fixed angular half-width of the shield in degrees."""
    shield_sizes: ShieldSizeConfig = field(
        default_factory=ShieldSizeConfig.peduks_fixed
    )


    # -- Reward --
    loss_factor: float = 0.003
    currency_symbol: str = "£"

    # -- Trigger settings --
    trigger_mode: str = "dummy"
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
    tone_freq_standard: float = 440.0
    tone_freq_deviant: float = 528.0
    tone_duration: float = 0.07
    """Duration of each tone (seconds)."""
    tone_volume: float = 1.0
    tone_isi_frames: int = 26
    """Inter-stimulus interval between successive tones (in frames).
    
    PEDUKS MMN default: 26 frames = ~433 ms at 60 Hz (matches MATLAB's 430 ms).
    """

    # -- Visual style --
    style: StimulusStyle = field(default_factory=StimulusStyle)

    # -- Session structure --
    enable_practice: bool = True
    """Whether to run the practice session before the main experiment."""

    reset_reward_after_practice: bool = True
    """Reset session reward to 0 after practice ends."""

    n_blocks: int = 4
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
