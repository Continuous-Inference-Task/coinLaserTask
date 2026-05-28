# CoIn Laser Task — Save the World

PsychoPy-based experiment for the Continuous Inference (CoIn) study's laser task.
This repository contains a unified Python codebase integrating the experiment runner, laser stimulus sequence generator, and auditory MMN tone player.

---

## 🚀 Interactive Configuration & Setup Wizard

The repository features a centralized CLI management tool: **`setup.py`**. Instead of manually editing configuration files, you can manage the entire experimental environment interactively.

### Quick Start (Cross-Platform)

The project includes a smart cross-platform bootstrap script, **`run.py`**, which automatically creates a virtual environment, installs dependencies from `requirements.txt`, and launches the task setup wizard.

```bash
# Clone the repository, navigate into the directory, and run:
python run.py
```

This should work out-of-the-box on **Windows, macOS, and Linux** with no manual virtual environment setup or package installation required.

### CLI Options

Any arguments passed to `run.py` are forwarded directly to the configuration wizard:

- `python run.py` — Opens the interactive configuration menu.
- `python run.py --full` — Starts the step-by-step onboarding wizard for all sections.
- `python run.py --preset NAME` — Loads a study-design preset, then only prompts for machine-local settings (monitor, keys, triggers).
- `python run.py --report` — Displays a complete configuration printout.
- `python run.py --generate [--verify]` — Regenerates experimental sequences (and verifies them if `--verify` is included).
- `python run.py --reinstall` — Forces a clean reinstallation of all dependencies in the virtual environment.
- `python run.py --help` — Shows the helper/usage message.

### Experiment Presets

A **preset** is a JSON file in `presets/` that locks in the study design (shield, reward, audio, block design, etc.). When you load a preset, you only configure machine-specific settings.

```bash
# Interactive: pick a preset from the menu
python run.py
# → choose "1) Load Preset"

# Direct: load a specific preset by name
python run.py --preset PEDUKS_default
```

You can save your current configuration as a new preset from the interactive menu (option `p`). The resulting JSON file can be committed to git and shared with other researchers, who can then reproduce your exact study design on their own hardware.

---

## 📁 Repository Structure

```
coin_laser_task/
├── setup.py                   # Central CLI onboarding & configuration wizard
├── run.py                     # Cross-platform bootstrap script (venv setup, installs packages)
├── main.py                    # Experiment entry point (runs the PsychoPy interface)
├── requirements.txt           # Python package dependencies
├── README.md                  # Project documentation
│
├── presets/                  # Study-design presets (JSON, committed to git)
├── laserTask/                 # Experiment Engine (PsychoPy)
│   ├── config.py              #   Configuration loader (ExperimentConfig & StimulusStyle)
│   ├── dialog.py              #   PyQt6 setup dialog replacing legacy wxWidgets
│   ├── experiment.py          #   Core trial, block, and session execution logic
│   ├── stimuli.py             #   Visual components (shield, laser, Earth, icons)
│   ├── audio.py               #   Dynamic MMN auditory tone scheduler
│   ├── io.py                  #   Input/output file helpers
│   ├── reward.py              #   Reward tracking, hit/miss calculations, and framing
│   ├── shield.py              #   Shield mechanics (fixed/adjustable sizes)
│   └── triggers.py            #   Hardware trigger interface (Serial/Parallel/LSL/Dummy)
│
├── stimgen/                   # Offline Sequence Generation Scripts
│   ├── laser/                 #   Laser stimulus sequence generator
│   └── mmn/                   #   Auditory MMN design and generation scripts
│
├── images/                    # Visual assets (e.g., source icons, Earth background)
├── sequences/                 # Generated experimental sequences (ignored by git)
└── data/                      # Output directory for participant logs and CSV files
```

---

## ⚙️ Configuration Categories

Through `setup.py` (or manual edits in `laserTask/config.py`), you can configure:

1. **Machine & Target OS Setup**: Target OS (Linux/Windows), screen resolution, refresh rate, fullscreen toggle, and input devices (keyboard vs. MEG response box).
2. **Experiment & Practice Settings**: Number of blocks, block duration, and enabling/disabling the practice block (including detailed instruction/feedback screens).
3. **Shield & Reward Design**: Fixed or adjustable shield sizes, key mapping (default `f`/`j` on Linux, `1`/`2`/`3` on response boxes), framing profiles, and currency symbol.
4. **Auditory MMN Settings**: Sound frequencies (standards vs. deviants), volume level, play durations, and Inter-Stimulus Intervals (ISI).
5. **EEG/MEG Trigger Interface**: Trigger mode (Parallel port, Serial port, LSL, or Dummy/None) along with hardware port addresses.

---

## 🎮 Instructions & Practice Block

The unified task features an integrated **Practice Mode** with screen-by-screen walkthrough instructions:

- **Practice Start Screen**: Explains the task goals, practice duration (dynamically calculated), keys, and reward bar behavior.
- **Trial & Feedback**: A practice run where participants learn to maneuver the shield.
- **Post-Practice Explanation**: Summarizes key strategies (energy loss from unnecessary movement, handling volatile attack angles).
- **Audio Tones**: Warns participants that task-unrelated MMN tones will be played in the background during the main session.

---

## 🛡️ Pre-flight Verification Checks

To guarantee scientific accuracy and prevent runtime failures, the runner automatically performs the following checks before starting:

1. **Refresh Rate Warning**: Warns if the monitor refresh rate deviates from **60 Hz** (to prevent stimulus timing distortion).
2. **Min Laser Duration Validation**: Analyzes pre-loaded sequences to ensure the configured minimum laser duration does not exceed the shortest run length in the blocks (prevents overlaps/conflicts).

---

## 🧪 Running Tests

Validate both sequence generators and task components using the test suite:

**On macOS/Linux:**

```bash
# Run laser sequence generator tests
./stw/bin/python stimgen/laser/test_all.py

# Run MMN tone generator tests
./stw/bin/python -m pytest stimgen/mmn
```

**On Windows:**

```cmd
# Run laser sequence generator tests
stw\Scripts\python stimgen/laser/test_all.py

# Run MMN tone generator tests
stw\Scripts\python -m pytest stimgen/mmn
```

---

## 💳 Credits

Based on the original task design for the PEDUKS study.
_Contact: lilian.weber@psych.ox.ac.uk_
