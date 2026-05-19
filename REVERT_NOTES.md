# Portable Experiment Infrastructure Reference & Revert Notes

This document keeps track of the main behavioral modifications made to the `coin_laser_task` experiment during stabilization on Linux, and how they can be reverted if the researchers prefer the original/legacy behaviors.

---

## 1. Simultaneous Key Inputs
*   **Behavioral Change:** Replaces Pyglet's naive key-release event handler (which stopped movement if *any* key was released) with a robust list-based key state tracker (`active_keys`). Releasing one key now correctly resumes movement in the direction of another key that remains physically held down.
*   **Commit:** `2e287244e53fc6f334f25ea3d76c7f3d9a1b1b79` (marked as `feat(controls): implement robust multi-key state tracker for simultaneous inputs`)
*   **Reversion / Discussion:**
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
