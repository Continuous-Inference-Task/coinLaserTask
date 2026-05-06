# CoIn Laser Task — Save the World

PsychoPy-based experiment for the CoIn (Continuous Inference) study's laser task.
This is the unified Python codebase combining the experiment runner, laser stimulus generator,
and MMN tone sequence generator.

## Repository Structure

```
coin_laser_task/
├── main.py                    # Experiment entry point — run this to start
├── laserTask/                 # Experiment engine (PsychoPy)
│   ├── config.py              #   ExperimentConfig + StimulusStyle settings
│   ├── experiment.py          #   Main trial/block/session logic
│   ├── stimuli.py             #   Visual elements (shield, laser, icons)
│   ├── audio.py               #   Background MMN tone player
│   ├── io.py                  #   CSV loading, path construction, save
│   ├── reward.py              #   Reward tracking (hits, misses, framing)
│   ├── shield.py              #   Shield mechanics & size configs
│   └── triggers.py            #   MEG/EEG trigger manager (serial/parallel/lsl)
│
├── stimgen/                   # Sequence generation (offline — run before experiment)
│   ├── laser/                 #   Laser stimulus sequences
│   │   ├── config.py          #     ← Parameters: volatility, noise, durations
│   │   └── coin_script_sequence_generation.py  # Entry: generates all sessions
│   └── mmn/                   #   MMN tone sequences
│       ├── mmn_design.py      #     ← Parameters: tone freqs, probabilities
│       └── generate_all_peduks_sessions.py      # Entry: generates all tone blocks
│
├── images/                    # Visual assets (source icons, instructions)
├── sequences/                 # Generated CSVs consumed by the experiment at runtime
│   ├── coin_main_v4_order1/   #   Counterbalanced laser sequences
│   ├── ...                    #
│   └── mmn/                   #   Tone identity sequences (mmn_v1_block*.csv)
│
└── data/                      # Runtime output (participant data, logs)
```

## ⚠️ Configuration: Two Config Files

There are **two separate config files** — do not confuse them:

| File | Controls | When it matters |
|---|---|---|
| **`stimgen/laser/config.py`** | Noise levels, jump durations, block counts, volatility design, output path | **When generating sequences** (offline, before the experiment) |
| **`laserTask/config.py`** | Window size, keys, shield sizes, tone frequencies, paths, trigger mode | **When running the experiment** |

The two files have **matching version strings** that must stay in sync:
- `stimgen/laser/config.py` → `VERSION` / `VERSION_PRACTICE`
- `laserTask/config.py` → `sequence_version` / `practice_sequence_version`

---

## Quick Start

### 1. Setup

```bash
cd coin_laser_task

# Create virtual environment
python3 -m venv stw
source stw/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Generate Sequences (once, before running participants)

```bash
# Generate laser stimulus sequences
cd stimgen/laser
python coin_script_sequence_generation.py
cd ../..

# Generate MMN tone sequences
cd stimgen/mmn
python generate_all_peduks_sessions.py
cd ../..
```

This populates `sequences/` with CSV files the experiment reads at runtime.

### 3. Run the Experiment

```bash
python main.py
```

A dialog will prompt for participant ID, visit, session, order, and framing.

---

## Experiment Design

The "Save the World" task asks participants to manoeuvre a shield around a circle
to catch radiation beams emitted from a radioactive source.

- **4 main blocks** (3 min each) + 1 practice block (1 min)
- Two sources differ in **volatility** (how often the mean jumps)
- Background **MMN tones** play concurrently:
  - Standard: 440 Hz, 70 ms
  - Deviant: 528 Hz, 70 ms
  - ISI: ~430 ms (26 frames at 60 Hz)
- Shield size can be fixed or adjustable (configurable)

### Counterbalancing

Sequences use 4 orders across 2 sessions. The experiment framework is
condition-agnostic — all structure is defined by the generated CSV files.

| Order | Starts With | Source Images |
|---|---|---|
| 1 | Stable | vol=red |
| 2 | Volatile | vol=red |
| 3 | Stable | vol=blue |
| 4 | Volatile | vol=blue |

---

## Customization

### Before generating sequences

Edit **`stimgen/laser/config.py`** to adjust:
- Block durations, number of blocks
- Noise levels (`NOISE_STD_LOW`, `NOISE_STD_HIGH`)
- Jump duration distributions
- Output path (`OUTPUT_DIR`)

### Before running the experiment

Edit **`laserTask/config.py`** or pass overrides in **`main.py`** (`ExperimentConfig(...)`):
- Display: `fullscreen`, `window_size`, `monitor_name`, `screen_index`
- Controls: `key_left`/`key_right`, `input_device` (keyboard vs response box)
- Shield: `allow_shield_adjustment`, `shield_sizes` (via `ShieldSizeConfig`)
- Audio: `enable_audio`, `tone_freq_*`, `tone_duration`, `tone_isi_frames`
- Triggers: `trigger_mode` (serial/parallel/lsl/dummy)
- Reward: `currency_symbol`, framing profiles per shield size

---

## Running Tests

```bash
# Laser stimgen tests
cd stimgen/laser && python test_all.py

# MMN stimgen tests
cd stimgen/mmn && python -m pytest tests/
```

---

## Requirements

- Python ≥ 3.9
- PsychoPy (tested with v2022.1.2+)
- For MEG: appropriate trigger hardware / LSL setup

---

## Credits

Based on the original PEDUKS study task. Contact lilian.weber@psych.ox.ac.uk for questions.

*Python refactor & unification: Felix.*
