# Configuration Reference — CoIn Laser Task

Complete reference for every configurable parameter.  
Configure via `python setup.py` (recommended) or by editing the files directly.

---

## config_shared.py

Shared across both the experiment and the stimulus generator.

| Parameter | Default | Description |
|---|---|---|
| `SEQUENCE_VERSION` | `"v4"` | Version tag for main session sequences |
| `PRACTICE_SEQUENCE_VERSION` | `"v3"` | Version tag for practice session sequences |
| `SEQUENCE_ROOT` | `"sequences/"` | Output directory for generated CSVs (relative to project root) |

---

## laserTask/config.py — ExperimentConfig

All runtime experiment behaviour. Edit via `setup.py` sections 1–6 & 8, or directly.

### Display

| Field | Default | Setup section | Description |
|---|---|---|---|
| `target_os` | `"linux"` | 1 | Target OS (`linux`, `windows`, `macos`). Affects keyboard backend auto-selection. |
| `window_size` | `(1512, 982)` | 1 | Window dimensions in pixels (windowed mode only). |
| `fullscreen` | `True` | 1 | Fullscreen toggle. |
| `screen_index` | `0` | 1 | Which monitor to use (0 = primary). |
| `monitor_name` | `"testMonitor"` | 1 | PsychoPy monitor calibration name. |
| `background_color` | `[0, 0, 0]` | — | RGB background colour (black). |
| `target_refresh_rate` | `60` | 1 | Expected refresh rate in Hz. |

### Input

| Field | Default | Setup section | Description |
|---|---|---|---|
| `input_device` | `"keyboard"` | 2 | `"keyboard"` or `"response_box"`. Affects on-screen instructions. |
| `key_left` | `"f"` | 2 | Key to rotate shield left. |
| `key_right` | `"j"` | 2 | Key to rotate shield right. |
| `keyboard_backend` | `""` (auto) | — | PsychoPy keyboard backend: `"ptb"`, `"event"`, `"iohub"`. Auto-selects `"ptb"` on Windows, `"iohub"` otherwise. |
| `use_legacy_key_tracking` | `True` | — | Legacy key tracking behaviour for backward compatibility. |

### Shield

| Field | Default | Setup section | Description |
|---|---|---|---|
| `rotation_speed` | `1.0` | 5 | Degrees per frame the shield rotates while a key is held. |
| `circle_radius` | `3.0` | 5 | Radius of the game area in PsychoPy height units. |
| `allow_shield_adjustment` | `False` | 5 | If `True`, participant can grow/shrink the shield during the task. |
| `loss_factor` | `0.003` | 5 | Reward scaling factor applied to miss penalties. |
| `currency_symbol` | `"€"` | 5 | Currency symbol shown to the participant. |

### Shield sizes

Controlled via `ShieldSizeConfig`. Two presets are available:

**`peduks_fixed`** (default) — one fixed 20° shield:
- Hit (win framing): +`loss_factor`
- Miss (both framings): −`loss_factor`
- Hit (loss framing): 0

**`adjustable_standard`** — three sizes (10°, 20°, 30°):
- Small (10°): hit +loss_factor, miss −loss_factor
- Medium (20°): hit +⅔·loss_factor (win) / −⅓·loss_factor (loss), miss −loss_factor
- Large (30°): hit +½·loss_factor (win) / −½·loss_factor (loss), miss −loss_factor

### Reward

| Field | Default | Setup section | Description |
|---|---|---|---|
| `currency_symbol` | `"€"` | 5 | Displayed currency symbol. |
| `loss_factor` | `0.003` | 5 | Base reward increment (used by shield size calculations). |

### Audio (MMN tones)

| Field | Default | Setup section | Description |
|---|---|---|---|
| `enable_audio` | `True` | 6 | Master toggle for background tones. Tones play during main blocks only. |
| `tone_freq_standard` | `440.0` | 6 | Standard tone frequency in Hz. |
| `tone_freq_deviant` | `528.0` | 6 | Deviant tone frequency in Hz. |
| `tone_duration` | `0.07` | 6 | Tone length in seconds (70 ms). |
| `tone_volume` | `1.0` | 6 | Volume (0.0–1.0). |
| `tone_isi_frames` | `26` | 6 | Inter-stimulus interval in frames (~433 ms at 60 Hz). |

### Triggers (EEG/MEG)

| Field | Default | Setup section | Description |
|---|---|---|---|
| `trigger_mode` | `"dummy"` | 3 | `"dummy"` (console), `"serial"`, `"parallel"`, or `"lsl"`. |
| `serial_port` | `"/dev/ttyUSB0"` | 3 | Serial port path (auto-detected per OS if empty). |
| `serial_baud_rate` | `115200` | 3 | Serial baud rate. |
| `serial_timeout` | `0.001` | — | Serial timeout in seconds. |
| `parallel_address` | `"/dev/parport0"` | 3 | Parallel/LPT port address. |

### Experiment structure

| Field | Default | Setup section | Description |
|---|---|---|---|
| `enable_practice` | `True` | 4 | Whether to run a practice session before main blocks. |
| `show_earth_background` | `True` | 4 | Show the earth/world image behind the game. Disable for plain black. |
| `reset_reward_after_practice` | `True` | 4 | Reset reward counter to zero when main session starts. |
| `min_laser_duration_frames` | `6` | 5 | Laser positions shorter than this are merged (100 ms at 60 Hz). |
| `n_blocks` | `1` | — | Fallback block count (real count comes from stimulus generation config). |

### Dialog

| Field | Default | Setup section | Description |
|---|---|---|---|
| `dialog_fields` | `["participant", "visit", "session", "order", "framing", "practice_mode"]` | 8 | Fields shown in the session startup dialog. |
| `visits` | `["1", "2"]` | 8 | Dropdown options for Visit. |
| `sessions` | `["1", "2"]` | 8 | Dropdown options for Session. |
| `orders` | `["1", "2"]` | 8 | Dropdown options for Counterbalancing Order. |
| `framings` | `["loss", "win"]` | 8 | Dropdown options for Framing. |

### Visual style

Controlled via `StimulusStyle` dataclass. Not exposed in `setup.py` — edit directly in `laserTask/config.py`.

See the `StimulusStyle` dataclass for colour, size, and position of every visual element (shield, laser, source icon, reward bar, progress bar, text).

---

## stimgen/laser/config.py — Stimulus Generation

All stimulus generation parameters. Edit via `setup.py` section 7, or directly.

### Session structure

| Parameter | Default | Description |
|---|---|---|
| `MAIN_SESSION["nBlocks"]` | `1` | Number of blocks for main/baseline/infusion sessions. |
| `MAIN_SESSION["blockDurationMin"]` | `1` | Duration per block in minutes. |
| `PRACTICE_SESSION["nBlocks"]` | `4` | Number of blocks for practice. |
| `PRACTICE_SESSION["blockDurationMin"]` | `2` | Duration per practice block in minutes. |
| `DEFAULT_SESSION` | `{"nBlocks": 12, "blockDurationMin": 3}` | Fallback for legacy `generate_laser_session` calls. |

> **Total experiment time** = practice blocks × practice duration + main blocks × main duration.  
> Example with defaults: 4 × 2 min + 1 × 1 min = 9 minutes.

### Noise & volatility

| Parameter | Default | Description |
|---|---|---|
| `NOISE_STD_LOW` | `10` | Observation noise standard deviation in degrees (low condition). |
| `NOISE_STD_HIGH` | `20` | Observation noise standard deviation in degrees (high condition). |
| `JUMP_DURATION_MEAN_SEC` | `0.3` | Mean time the true mean stays at one position. |
| `JUMP_DURATION_MIN_SEC` | `0.075` | Minimum jump duration. |
| `JUMP_DURATION_MAX_SEC` | `1.0` | Maximum jump duration. |
| `JUMP_VALUE_SET` | `[-40, -30, -20, 20, 30, 40]` | Allowed jump sizes in degrees. |
| `SAMPLE_RATE` | `60` | Sequence generation sample rate (Hz). Must match monitor refresh. |

### Block conditions (advanced)

| Parameter | Default | Description |
|---|---|---|
| `DUR_MEAN_STD_MIN_MAX_STABLE` | `[10, 1.5, 8, 15]` | Epoch duration params for stable volatility. |
| `DUR_MEAN_STD_MIN_MAX_VOLATILE` | `[3, 1.5, 2, 6]` | Epoch duration params for volatile condition. |

These control the distribution of epoch lengths within each block type. Only change if you understand the underlying jump-design algorithm.

---

## Trigger Codes

Sent via the configured trigger backend during the experiment.

| Code | Name | When |
|---|---|---|
| `100` | `exp_start` | Experiment begins |
| `101` | `exp_end` | Experiment ends |
| `80` | `block_start` | Each block starts |
| `90` | `block_end` | Each block ends |
| `99` | `last_frame` | Final frame of each block |
| `10` | `laser_hit` | Shield absorbs the laser |
| `20` | `laser_miss` | Laser misses the shield |
| `30` | `key_right` | Right key pressed |
| `40` | `key_left` | Left key pressed |
| `50` | `key_release` | Shield rotation change (key release) |
| `1` | `tone_standard` | Standard tone onset |
| `2` | `tone_deviant` | Deviant tone onset |
| `60` | `shield_shrink` | Shield resized smaller (adjustable mode) |
| `70` | `shield_grow` | Shield resized larger (adjustable mode) |

---

## Direct Config Editing

If you prefer editing files directly over the wizard:

1. **Runtime settings**: Edit `laserTask/config.py` — change the `ExperimentConfig` dataclass fields.
2. **Stimulus generation**: Edit `stimgen/laser/config.py`.
3. **Regenerate sequences**: `cd stimgen/laser && python coin_script_sequence_generation.py`
4. **Shared settings**: Edit `config_shared.py`.

> After editing stimgen config, you must regenerate sequences for changes to take effect.

---

## Experiment Presets

A preset is a JSON file in `presets/` that captures configuration values so they can be shared and reproduced. **Any field can go in a preset** — the setup wizard automatically detects which sections are fully covered (locked) and which are open, then only prompts you for the open ones.

### How routing works

The wizard maps config fields to 8 sections. If a preset contains **all** fields for a section, that section is locked (skipped). If any field is missing, the section is open (you'll be prompted).

| § | Section | Namespace | Fields |
|---|---|---|---|
| 1 | Machine setup | experiment | `target_os`, `window_size`, `fullscreen`, `screen_index`, `monitor_name`, `target_refresh_rate` |
| 2 | Input & controls | experiment | `input_device`, `key_left`, `key_right`, `use_legacy_key_tracking` |
| 3 | Triggers & hardware | experiment | `trigger_mode`, `serial_port`, `serial_baud_rate`, `parallel_address` |
| 4 | Experiment design | experiment | `enable_practice`, `show_earth_background`, `reset_reward_after_practice` |
| 5 | Shield & reward | experiment | `allow_shield_adjustment`, `fixed_shield_degrees`, `rotation_speed`, `circle_radius`, `loss_factor`, `currency_symbol`, `min_laser_duration_frames` |
| 6 | Auditory MMN | experiment | `enable_audio`, `mmn_type`, `tone_freq_standard`, `tone_freq_deviant`, `tone_duration`, `tone_duration_standard`, `tone_duration_deviant`, `tone_isi_frames`, `tone_volume` |
| 7 | Sequence generation | stimgen | `PRACTICE_VOLATILITY`, `PRACTICE_NOISE`, `PRACTICE_NOISE_MODE`, `PRACTICE_N_SESSIONS`, `PRACTICE_BLOCK_DURATION_MIN`, `MAIN_VOLATILITY`, `MAIN_NOISE`, `MAIN_NOISE_MODE`, `MAIN_N_SESSIONS`, `MAIN_BLOCK_DURATION_MIN`, `JUMP_DURATION_MEAN_SEC`, `JUMP_DURATION_MIN_SEC`, `JUMP_DURATION_MAX_SEC`, `JUMP_VALUE_SET` |
| 8 | Startup dialog | experiment | `dialog_fields`, `visits`, `framings` |

A preset that includes sections 4–8 locks the study design and only prompts for machine settings (1–3). A preset that includes all 8 sections locks everything. A minimal preset that only includes section 7 still lets you configure everything else interactively.

### Usage

```bash
# Interactive preset picker
python setup.py
# → choose "1) Load Preset"

# Direct preset load (skip the picker)
python setup.py --preset PEDUKS_default

# Save current config as a preset (from the interactive menu, press 'p')
python setup.py
```

### Preset JSON format

```json
{
    "name": "PEDUKS_default",
    "description": "PEDUKS study replication — fixed 20° shield, duration MMN",
    "notes": "Optional notes shown in the summary",
    "experiment": {
        "enable_practice": true,
        "allow_shield_adjustment": false,
        "fixed_shield_degrees": 20.0,
        "...": "(any experiment fields — only included ones are locked)"
    },
    "stimgen": {
        "MAIN_VOLATILITY": ["stable", "volatile"],
        "MAIN_NOISE": ["noisy"],
        "JUMP_VALUE_SET": [-40, -30, -20, 20, 30, 40],
        "...": "(any stimgen fields — only included ones are locked)"
    }
}
```

When saving a preset from the menu, you choose which sections to lock. Study-design sections (4–8) are pre-selected; machine-local sections (1–3) are off by default but can be added.

Commit preset files to git to share them. Other researchers clone the repo, pick the preset, and configure only the open sections.
