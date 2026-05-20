# CoIn Laser Task — Save the World

PsychoPy experiment for the Continuous Inference (CoIn) study.  
Participants rotate a shield to deflect laser beams, earning rewards for hits and losing them for misses.

---

## 🚀 Quick Start

```bash
# 1. Create virtual environment & install dependencies
python3 -m venv stw
source stw/bin/activate          # Linux/macOS
# stw\Scripts\activate           # Windows
pip install -r requirements.txt

# 2. Configure the experiment
python setup.py

# 3. Generate sequences
#    (setup.py will offer to do this after configuration)

# 4. Run the experiment
python main.py
```

### One-command workflows

```bash
python setup.py --report     # Print current config without prompts
python setup.py --generate   # Regenerate sequences from current config only
python setup.py --full       # Full step-by-step wizard (all sections)
python setup.py --help       # Show all options
```

---

## 📖 How to use this repository

### The two config files (and why there are two)

| File | What it controls | How to edit |
|---|---|---|
| `laserTask/config.py` | **Runtime** — display, keys, shield, reward, audio, triggers | `python setup.py` or edit directly |
| `stimgen/laser/config.py` | **Stimulus generation** — number of blocks, block duration, noise levels | Section 7 of `setup.py` or edit directly |
| `config_shared.py` | **Shared** — sequence version numbers and output directory | Edit directly |

> **Important**: The number of blocks is configured in **Section 7** (Sequence Generation) of `setup.py`, not in Section 4 (Experiment Design). Section 4's `n_blocks` was removed to avoid confusion — there is now a single source of truth.

### Typical workflow

1. **First time**: `python setup.py` → walk through each numbered section
2. **Adjust design**: Re-run specific sections (e.g., `7` for block counts)
3. **Regenerate**: Setup offers to regenerate sequences after changes
4. **Run**: `python main.py` launches the PsychoPy experiment

### Session dialog

The startup dialog asks for:
- **Participant ID** — numeric (e.g. `1001`)
- **Visit** — dropdown (1 or 2)
- **Session** — dropdown (1 or 2)
- **Order** — counterbalancing order (1–2)
- **Framing** — `loss` or `win` (does the participant try to avoid loss or gain reward?)
- **Practice only** — if checked, only the practice session runs

> The dialog fields shown can be customized in Section 8 of `setup.py`.

---

## 📁 Repository Structure

```
coin_laser_task/
├── setup.py                   # CLI setup & configuration wizard
├── main.py                    # Experiment entry point
├── config_shared.py            # Shared version/reference strings
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── CONFIG.md                  # Complete config reference (all options)
├── comprehensive_test.py      # Integration & regression tests
│
├── laserTask/                 # Experiment engine (PsychoPy)
│   ├── config.py              #   ExperimentConfig & StimulusStyle
│   ├── experiment.py          #   Trial, block, and session logic
│   ├── stimuli.py             #   Visual components (shield, laser, earth, icons)
│   ├── audio.py               #   MMN tone scheduler
│   ├── io.py                  #   File I/O helpers
│   ├── reward.py              #   Reward tracking & framing
│   ├── shield.py              #   Shield mechanics
│   └── triggers.py            #   Hardware trigger interface
│
├── stimgen/                   # Offline sequence generation
│   ├── laser/                 #   Laser stimulus generator
│   │   ├── config.py          #     Generation parameters
│   │   ├── coin_script_sequence_generation.py  #  Main entry point
│   │   └── test_all.py        #     Unit tests
│   └── mmn/                   #   Auditory MMN generator
│
├── images/                    # Visual assets
├── sequences/                 # Generated sequences (gitignored)
└── data/                      # Participant output (gitignored)
```

---

## 🧪 Testing

```bash
# Comprehensive integration tests
python comprehensive_test.py

# Laser stimulus generator unit tests
cd stimgen/laser && python test_all.py

# MMN tone generator tests  
cd stimgen/mmn && python -m pytest tests/

# All together
python comprehensive_test.py && cd stimgen/laser && python test_all.py
```

---

## ⚙️ Configuration

See **[CONFIG.md](CONFIG.md)** for a complete reference of every configurable parameter, including:
- All `ExperimentConfig` fields with defaults and explanations
- All `stimgen/laser/config.py` parameters
- Shield mechanics and framing details
- Trigger setup for EEG/MEG
- Advanced: direct config file editing

---

## 💳 Credits

Based on the original task design for the PEDUKS study.  
*Contact: lilian.weber@psych.ox.ac.uk*  
*Refactored & Unified: Felix.*
