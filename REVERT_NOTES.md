# Portable Experiment Infrastructure Reference & Revert Notes

This document keeps track of the main behavioral modifications made to the `coin_laser_task` experiment during stabilization on Linux, and how they can be reverted if the researchers prefer the original/legacy behaviors.

---

## 1. Simultaneous Key Inputs
*   **Behavioral Change:** Replaces Pyglet's naive key-release event handler (which stopped movement if *any* key was released) with a robust list-based key state tracker (`active_keys`). Releasing one key now correctly resumes movement in the direction of another key that remains physically held down.
*   **Commits:**
    *   `2e28724` — `feat(controls): implement robust multi-key state tracker for simultaneous inputs`
    *   *(latest)* — `fix(controls): emit key_release trigger on partial key release` (Hybrid Trigger Sequence — Option A)
*   **How Legacy Key Tracking is Impaired / Changed:**
    1.  **Missing `key_release` Triggers  →  FIXED via Option A:** In the original script, releasing *any* key sent a `key_release` trigger (`50`). The multi-key tracker initially omitted `key_release` when one key was released while another was still held. The **Hybrid Trigger Sequence** fix restores the `key_release` trigger: whenever a key is released while another remains held, `key_release (50)` is emitted via `trig.send()` and a direction trigger immediately follows so the stream reads ``… → key_release(50) → key_<dir>(30/40) → …``. Additionally, the direction-trigger gate now matches the original: intermediate direction changes during multi-key overlap are **suppressed** (``send_resp_triggers`` gate), identical to the original silent frames. The resulting trigger stream is byte-for-byte identical to the original — analysis scripts that parse alternating ``press → release → press`` sequences will work correctly.
    2.  **Continuous Movement (No Stationary Phases):** In the original version, releasing one of two simultaneously held keys would flush the keyboard queue, leaving the shield stationary until all keys were lifted and a new key was pressed. The new method automatically resumes movement in the direction of the remaining held key. Any mathematical model expecting the shield to come to a halt upon a key release will see a discrepancy in the trajectory coordinates.
*   **Alternative Compatibility Options:**
    *   **Option A: Hybrid Trigger Sequence ✓ IMPLEMENTED:** When a key is released while another remains held, `key_release` (50) is emitted immediately before the resumed direction trigger. This preserves the `press → release → press` event loop for legacy analysis scripts while maintaining smooth movement. See `experiment.py` — search for `"Hybrid trigger sequence"`.
    *   **Option B: Full-State CSV Logging:** We could add a dedicated CSV column logging the exact set of physically held keys (e.g., `"['k']"`, `"['k', 'd']"`) on every frame, allowing researchers to retrospectively analyze overlapping inputs without relying purely on trigger sequences. *(not yet implemented)*
*   **Reversion:**
    *   To revert **both** the multi-key tracker and the hybrid trigger fix (restore original naive-stop behavior):
        ```bash
        git revert <hybrid-trigger-commit>
        git revert 2e287244e53fc6f334f25ea3d76c7f3d9a1b1b79
        ```
    *   To revert **only** the hybrid trigger injection (keep smooth multi-key movement but remove injected `key_release` triggers):
        ```bash
        git revert <hybrid-trigger-commit>
        ```

---

## 2. Laser Rendering Depth & Tone Apodization
*   **Behavioral Change:**
    1.  **Laser Layering:** Corrected the depth sorting so that the laser renders *below* (underneath) the central radioactive source image, keeping the beginning of the beam cleanly masked. 
    2.  **Audio Tone Apodization:** Replaced a full-length Hamming window (which muffled the 70ms tones) with a 5ms Hanning ramp at the onset and offset (matching PsychoPy's native `apodize` function), restoring the crispness of standard and deviant beeps.
*   **Commit:** `2b231f6d338cbca41f5a54db68ec09774e1d1c81` (marked as `fix(visuals): draw laser below source image and match original PsychoPy 5ms tone apodization`)
*   **Reversion / Discussion:**
    *   If you need to revert the laser rendering depth or audio tone envelope fixes to match the original Python/Builder bug precisely:
        ```bash
        git revert 2b231f6d338cbca41f5a54db68ec09774e1d1c81
        ```
    *   *Note on the Laser Depth Bug:* In the original Builder code, the laser was drawn *below* the radioactive source image only on the very first frame of a block. As soon as the laser turned off and then back on for subsequent evidence, PsychoPy's dynamic `setAutoDraw(True)` call pushed it to the end of the drawing list, causing it to render *on top* of the radioactive image. We resolved this by keeping it in the drawing list permanently and using `setOpacity(1.0)` / `setOpacity(0.0)`.

---

## 3. Configurable Session Dialog Fields
*   **Behavioral Change:** The session setup dialog fields (which fields appear) are now controlled by `ExperimentConfig.dialog_fields` — a list of field names. Previously all five fields (`participant`, `visit`, `session`, `order`, `framing`) were always shown with no way to omit individual fields.
*   **Commit:** *(latest)* — `feat(config): make session dialog fields configurable via ExperimentConfig.dialog_fields`
*   **How It Works:**
    - `dialog_fields` is a list of field names in `ExperimentConfig`. Known fields (`"participant"`, `"visit"`, `"session"`, `"order"`, `"framing"`) get appropriate widgets (auto-detected ID, dropdowns). Unknown fields render as free-text inputs.
    - The dropdown **options** for known fields still come from the existing config properties (`cfg.visits`, `cfg.sessions`, `cfg.orders`, `cfg.framings`).
    - `"participant"` is force-included even if omitted (required for data-file naming).
*   **Example Usage in `main.py`:**
    ```python
    cfg = ExperimentConfig(
        dialog_fields=["participant", "visit", "session", "order"],  # no framing dropdown
        # ...
    )
    ```
*   **Reversion:**
    *   To restore the hardcoded five-field dialog:
        ```bash
        git revert <dialog-fields-commit>
        ```
    *   Or simply set `dialog_fields` to the full list (which is also the default):
        ```python
        dialog_fields=["participant", "visit", "session", "order", "framing"]
        ```
