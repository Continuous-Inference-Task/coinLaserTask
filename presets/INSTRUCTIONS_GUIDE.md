# Experiment Instructions Guide (Option 1)

This guide explains how to customize, reorder, and add instruction screens for the COIN Laser Task.

---

## 1. Directory Structure & Possible Files

Each study profile has a folder in `presets/` (e.g. `presets/cogpsy_instructions/`, `presets/sleps_instructions/`).

All files in this folder are **optional**. If a file is not present in your folder, the task automatically falls back to the clean built-in default text. You only need to create the files you want to customize!

### Complete List of Possible Files You Can Create:

| File Name | When It Appears | Description & Typical Content |
|---|---|---|
| **`pre_experiment.txt`** | Task launch (before any blocks) | Welcome screen, rules, shield controls, and reward mechanics. Use `---` to split into multiple pages! |
| **`pre_practice.txt`** | Before the practice block | Practice goals, duration, reminder of movement controls. |
| **`post_practice.txt`** | After the practice block | Feedback on practice, strategy advice for the real task. |
| **`pre_main.txt`** | Before the first main block | Transition into main experiment: MEG/EEG eye-fixation rules, background audio notes, source colour legend with `@image:`. Use `---` to split pages! |
| **`before_main_block.txt`** | Before each main block | Block counter (`Block {phase_block_idx} of {phase_block_total}`), source preview, eye-fixation reminder. |
| **`after_main_block.txt`** | After each main block | Break screen: feedback on block earnings, rest prompt, continue prompt. |
| **`post_experiment.txt`** | After all blocks finish | Final completion message, total session reward earned. |
| **`stop_recording.txt`** | After experiment completion | Operator safeguard prompt: holds LSL stream alive until LabRecorder is stopped. |

> **Framing Note:** For any file above, you can create `_loss.txt` and `_win.txt` variants (for example, `pre_experiment_loss.txt` and `pre_experiment_win.txt`). The task automatically loads the file matching the session's framing condition!

### Example Directory:
```
presets/cogpsy_instructions/
  ├── pre_experiment.txt       # Custom 3-page intro (welcome, shield, reward)
  └── pre_main.txt             # Custom 3-page main intro (tones, MEG rules, source legend)
  # (All other sections automatically use clean built-in defaults)
```
---

## 2. Multi-Page Screens: The `---` Page Divider

To split a section across multiple consecutive screens, simply add `---` on its own line:

```text
Welcome to the Save-the-world game!
Catch radiation beams with your shield.
Press 'SPACE' to continue.
---
Your shield can be positioned anywhere on a circle.
Use the '{key_left}' and '{key_right}' keys to navigate.
Press 'SPACE' to continue.
---
In every block, your reward starts at {currency}{initial_reward}.
{continue_prompt}
```

- **To add a page:** Add `---` and write the new page text.
- **To remove a page:** Delete the page and its `---` separator.
- The experiment advances to the next page when the participant presses the continue key (`SPACE`).
- **Data columns:** every page that waits for a key writes `<section>_<page>.key` and `<section>_<page>.rt` to the session data file, numbered from 1 even for single-page sections (`pre_practice_1.key`, `pre_main_3.rt`, `stop_recording_1.key`). Adding or removing pages therefore adds or removes columns, and keeping `_loss`/`_win` variants at the same page count keeps both framings' data files identical in layout. `post_experiment` is timed and writes no columns.

---

## 3. How to Embed Images: The `@image:` Line

To attach one or more images to any page, add `@image: <paths>` at the top of that page:

```text
@image: images/radioactive1.png, images/radioactive2.png
You will encounter two different radioactive sources:
A yellow and a blue source.

{continue_prompt}
```

- **Single image:** Displayed centered above the text. Wide banners automatically preserve their aspect ratio.
- **Two images:** Displayed side-by-side above the text.

---

## 4. Win vs. Loss Framing

To show different instructions depending on whether the participant is in the **win** or **loss** condition:

- Name the file ending in `_loss.txt` (e.g. `pre_experiment_loss.txt`).
- Name the file ending in `_win.txt` (e.g. `pre_experiment_win.txt`).

The task automatically loads the file matching the session's framing condition.

---

## 5. Available Runtime Placeholders

You can use any of these placeholders in your text files. They are automatically replaced with the session's actual values at runtime:

| Placeholder | Example Output | Description |
|---|---|---|
| `{key_left}` | `F` | Left movement key |
| `{key_right}` | `J` | Right movement key |
| `{key_next}` | `SPACE` | Key used to advance instructions |
| `{continue_prompt}` | `Press 'SPACE' to continue.` | Prompt text based on `key_next` |
| `{start_prompt}` | `Press 'SPACE' to start.` | Prompt text based on `key_next` |
| `{currency}` | `€` or `£` | Configured currency symbol |
| `{initial_reward}` | `1.00` or `2.00` | Starting reward for the block |
| `{loss_factor}` | `0.003` | Monetary loss/gain per frame |
| `{n_main_blocks}` | `4` | Total number of main blocks |
| `{block_duration_min}` | `4 min` | Duration of each main block |
| `{practice_duration_min}`| `2 min` | Duration of the practice block |
| `{phase_block_idx}` | `1` | Current block number within the phase |
| `{phase_block_total}` | `4` | Total blocks within the phase |
| `{block_reward}` | `€1.85` | Reward earned in the completed block |
| `{total_reward}` | `€3.70` | Total reward earned across the session |
| `{move_blurb}` | `"Use the 'F' key to move..."` | Device-appropriate movement instruction |
| `{tone_blurb}` | `"While playing the game, you will also hear tones..."` | Background-tone explanation; empty when `enable_audio` is off |
| `{shield_instructions}` | `"Shield Size ..."` | Full shield-size explanation page (keys, reward per size, continue prompt); empty when `allow_shield_adjustment` is off. A page containing only empty placeholders is skipped. |

---

## 6. How to Preview Instructions Visually

To inspect your instruction screens in an actual PsychoPy visual window:

```bash
# Open real visual window preview for CogPsy:
python -m laserTask.instructions --profile cogpsy

# Open visual window preview for SLEPS:
python -m laserTask.instructions --profile sleps

# Open visual window preview for standard PEDUKS:
python -m laserTask.instructions --profile default
```

Press **SPACE** to step through each slide, and **ESC** to exit.
If no display is connected (e.g. over remote SSH), it automatically falls back to printing the formatted screens in the terminal. You can also force terminal output with `--terminal`:

```bash
python -m laserTask.instructions --profile cogpsy --terminal
```
