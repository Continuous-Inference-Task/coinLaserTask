# Portable Experiment Infrastructure Reference & Revert Notes

This document keeps track of the main behavioral modifications made to the `coin_laser_task` experiment during stabilization on Linux, and how they can be reverted if the researchers prefer the original/legacy behaviors.

---

## 1. Simultaneous Key Inputs
*   **Behavioral Change:** Replaces Pyglet's naive key-release event handler (which stopped movement if *any* key was released) with a robust list-based key state tracker (`active_keys`). Releasing one key now correctly resumes movement in the direction of another key that remains physically held down.
*   **Commit:** `2e287244e53fc6f334f25ea3d76c7f3d9a1b1b79` (marked as `feat(controls): implement robust multi-key state tracker for simultaneous inputs`)
*   **How Legacy Key Tracking is Impaired / Changed:**
    1.  **Missing `key_release` Triggers:** In the original script, releasing *any* key sent a `key_release` trigger (`102`). In the new version, if a subject holds **K** (Right) and presses/releases **D** (Left) while keeping **K** held, no `key_release` trigger is emitted during the transition. The trigger sequence records an immediate direction switch: `press_right` -> `press_left` -> `press_right` without a `release` trigger in between. This can break legacy EEG/behavioral analysis parsing scripts that strictly expect alternating `press` and `release` event sequences.
    2.  **Continuous Movement (No Stationary Phases):** In the original version, releasing one of two simultaneously held keys would flush the keyboard queue, leaving the shield stationary until all keys were lifted and a new key was pressed. The new method automatically resumes movement in the direction of the remaining held key. Any mathematical model expecting the shield to come to a halt upon a key release will see a discrepancy in the trajectory coordinates.
*   **Alternative Compatibility Options:**
    *   **Option A: Hybrid Trigger Sequence (Recommended for compatibility):** If a key is released while another remains held, we can programmatically emit a `key_release` trigger *immediately before* emitting the trigger for the resumed direction (within the same frame or on the next frame). This preserves the `press -> release -> press` event loop for the analysis scripts while maintaining smooth movement for the user.
    *   **Option B: Full-State CSV Logging:** We could add a dedicated CSV column logging the exact set of physically held keys (e.g., `"['k']"`, `"['k', 'd']"`) on every frame, allowing researchers to retrospectively analyze overlapping inputs without relying purely on trigger sequences.
*   **Reversion:**
    *   If researchers prefer the original "naive stop" behavior (e.g. because modeling subject decision-making counts simultaneous releases as a full stop/reset), this commit can be easily reverted:
        ```bash
        git revert 2e287244e53fc6f334f25ea3d76c7f3d9a1b1b79
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
