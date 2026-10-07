# Experiment Instructions Guide

This guide explains how to customize, reorder, and add instruction screens for the COIN Laser Task.

---

## 1. One Folder per Study

Each study has its own instruction folder in `presets/`, selected by the preset's `instruction_dir` setting:

| Study | Folder |
|---|---|
| PEDUKS | `presets/peduks_instructions/` |
| CogPsy (Rob's version) | `presets/cogpsy_rob_instructions/` |
| CogPsy (original) | `presets/cogpsy_original_instructions/` |
| SLEPS | `presets/sleps_instructions/` |

**The folder is the complete list of screens.** There is no hidden built-in text: every screen a participant sees comes from a `.txt` file in the study's folder, and a section whose file is missing (or empty) is simply not shown. To change a screen, edit its file; to drop a screen, delete its file.

The task refuses to start if `instruction_dir` is not set or the folder does not exist, and - when the session uses LSL triggers - if `start_recording.txt` or `stop_recording.txt` is missing.

### Sections (one file each):

| File Name | When It Appears | Description & Typical Content |
|---|---|---|
| **`pre_experiment.txt`** | Task launch (before any blocks) | Welcome screen, rules, shield controls, and reward mechanics. Use `---` to split into multiple pages! |
| **`pre_practice.txt`** | Before the practice block | Practice goals, duration, reminder of movement controls. |
| **`post_practice.txt`** | After the practice block | Feedback on practice, strategy advice for the real task. |
| **`pre_main.txt`** | Before the first main block | Transition into main experiment: MEG/EEG eye-fixation rules, background audio notes, source colour legend with `@image:`. Use `---` to split pages! |
| **`before_main_block.txt`** | Before each main block | Block counter (`Block {phase_block_idx} of {phase_block_total}`), eye-fixation reminder. The block's source image is added automatically to pages without an `@image:` line; leave a run of 3+ blank lines where it should go. |
| **`after_main_block.txt`** | After each main block | Break screen: feedback on block earnings, rest prompt, continue prompt. |
| **`post_experiment.txt`** | After all blocks finish | Final completion message, total session reward earned. |
| **`start_recording.txt`** | Task launch, LSL triggers only | Operator screen shown before the first trigger: the LSL outlet already exists, so start LabRecorder (Update + select `LaserTask_Triggers`, Start Recording), then press RETURN. `exp_start` is sent right after. Required when `trigger_mode` is `lsl`. |
| **`stop_recording.txt`** | After experiment completion | Operator safeguard prompt: holds LSL stream alive until LabRecorder is stopped. Required when `trigger_mode` is `lsl`. |

> Both operator screens advance on **RETURN** (never the participant's `key_next`), and each one's keypress ends its own data row, so they never add spurious condition rows to the data file.

> **Framing Note:** For any file above, you can create `_loss.txt` and `_win.txt` variants (for example, `pre_experiment_loss.txt` and `pre_experiment_win.txt`). The task automatically loads the file matching the session's framing condition!

### Example Directory:
```
presets/sleps_instructions/
  ├── pre_experiment_loss.txt   # loss-framing intro
  ├── pre_experiment_win.txt    # win-framing intro
  ├── pre_practice.txt
  ├── post_practice.txt
  ├── pre_main.txt
  ├── before_main_block.txt
  ├── after_main_block.txt
  ├── post_experiment.txt
  ├── start_recording.txt      # LSL operator screen (launch)
  └── stop_recording.txt       # LSL operator screen (end)
```

### Starting a New Study (Wizard Walkthrough)

1. Start the wizard:
   ```bash
   uv run python wizard.py
   ```
2. In **Setup mode**, type `3` (**Advanced Settings**), then `9` (**Instructions & slide text**).
3. **Instruction folder** - lists every `presets/*_instructions/` folder. Highlighting one shows a short tip and how many of the 9 screens have text. Pick **+ new study folder**. (To just switch an existing setup to another study's text, pick that folder here instead and skip to step 6.)
4. **Start the new folder from** - the cursor starts on PEDUKS:
   - **an existing folder** (`peduks`, `cogpsy_rob`, `cogpsy_original`, `sleps`, ...): copies all of its files; good when your study is a variation of one of these. PEDUKS is the recommended starting point.
   - **start fresh (empty files)**: one empty `.txt` per screen, so you see every file name but write all text yourself. Empty files show nothing; only `start_recording.txt` and `stop_recording.txt` are pre-filled with the LabRecorder prompts.
5. **Name of the new study** - e.g. `mystudy` creates `presets/mystudy_instructions/` (letters, digits, `_`, `-`; existing names are refused).
6. The wizard lists which screens the folder will show and which have no file/text, and warns if `start_recording.txt` or `stop_recording.txt` is missing or empty. Answer **Preview instructions in terminal now?** with `y` to read them formatted.
7. **Save this section?** - `y` writes the folder to `laserTask/config.json`. Typing `back` instead discards the section's changes (a newly created folder stays on disk; delete it by hand if unwanted).
8. Edit the `.txt` files in the new folder, checking them with the preview commands in [section 6](#6-how-to-preview-instructions-visually).
9. To share the setup, choose `p` (**Save current config as preset**) in the menu. It saves what is in `config.json`, so do step 7 first. The wizard then prints the `git add` command for the preset JSON and the instruction folder - commit both together.

Menus: `↑`/`↓` (or `j`/`k`) and `Enter` to choose; `b` accepts the pre-selected entry without changing it. Text prompts: type `back` to leave the section without saving.

Loading a study preset (`1` **Load Preset** in the wizard, or `uv run python wizard.py --preset SLEPS_default`) sets its instruction folder automatically.

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
- The experiment advances to the next page when the participant presses the continue key: `key_next` if the config sets one (e.g. `SPACE`), otherwise **any key**.
- **Data columns:** every page that waits for a key writes `<section>_<page>.key` and `<section>_<page>.rt` to the session data file, numbered from 1 even for single-page sections (`pre_practice_1.key`, `pre_main_3.rt`, `stop_recording_1.key`). Adding or removing pages (or whole section files) therefore adds or removes columns, and keeping `_loss`/`_win` variants at the same page count keeps both framings' data files identical in layout. `post_experiment` is timed and writes no columns.

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
- **Where the image row goes:** the slide is a vertical stack *top text – image row – bottom text*. The image row is placed at the **longest run of 3+ consecutive blank lines** in the page text (first run wins on ties); if the page has no such run, the image row sits at the top with all text below it. Use blank lines to choose the split.

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
| `{key_next}` | `SPACE` | Key used to advance instructions; renders as `SPACE` when `key_next` is empty (and screens then accept any key) |
| `{continue_prompt}` | `Press 'SPACE' to continue.` | Prompt text based on `key_next` (`Press any key to continue.` when empty) |
| `{start_prompt}` | `Press 'SPACE' to start.` | Prompt text based on `key_next` (`Press any key to start.` when empty) |
| `{currency}` | `€` or `£` | Configured currency symbol |
| `{initial_reward}` | `1.00` or `2.00` | Starting reward for the block |
| `{loss_factor}` | `0.003` | Monetary loss/gain per frame |
| `{n_main_blocks}` | `4` | Total number of main blocks |
| `{blocks_word}` | `block` / `blocks` | `block` when `{n_main_blocks}` is 1, else `blocks` - for singular/plural in a sentence |
| `{block_duration_min}` | `4 min` | Duration of each main block |
| `{practice_duration_min}`| `2 min` | Duration of the practice block |
| `{phase_block_idx}` | `1` | Current block number within the phase |
| `{phase_block_total}` | `4` | Total blocks within the phase |
| `{block_reward}` | `€1.85` | Reward earned in the completed block |
| `{total_reward}` | `€3.70` | Total reward earned across the session |
| `{framing}` | `loss` | The session's framing condition (`loss` or `win`) |
| `{source_image_path}` | `images/radioactive1.png` | The current block's source image path, as used by `before_main_block` screens (also what the auto-added image uses) |
| `{move_blurb}` | `"Use the 'F' key to move..."` | Device-appropriate movement instruction |
| `{tone_blurb}` | `"While playing the game, you will also hear tones..."` | Background-tone explanation; empty when `enable_audio` is off |
| `{shield_instructions}` | `"Shield Size ..."` | Full shield-size explanation page (keys, reward per size, continue prompt); empty when `allow_shield_adjustment` is off. A page containing only empty placeholders is skipped. |

---

## 6. How to Preview Instructions Visually

To inspect your instruction screens in an actual PsychoPy visual window:

```bash
# Preview a study preset (its instruction folder, keys, currency, rewards, durations):
uv run python -m laserTask.instructions --preset presets/SLEPS_default.json
uv run python -m laserTask.instructions --preset presets/Cogpsy_Rob_Version_2026.json
uv run python -m laserTask.instructions --preset presets/PEDUKS_default.json

# Preview a folder with the active config.json settings (e.g. while editing a new study):
uv run python -m laserTask.instructions --dir presets/mystudy_instructions/
```

`--dir` can be combined with `--preset` to show a folder with another preset's settings. `--framing loss|win` limits the preview to one framing (default: both).

Step through each slide with the advance key the config sets (`SPACE` when `key_next` is `space`; **any key** when `key_next` is empty), and **ESC** to exit.
If no display is connected (e.g. over remote SSH), it automatically falls back to printing the formatted screens in the terminal. You can also force terminal output with `--terminal`:

```bash
uv run python -m laserTask.instructions --preset presets/SLEPS_default.json --terminal
```
