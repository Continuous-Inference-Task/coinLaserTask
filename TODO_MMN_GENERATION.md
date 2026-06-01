# MMN sequence generation cleanup

## Background

`stimgen/mmn/generate_block_sequence.py` uses rejection sampling in
`_generate_stable_sequence` to enforce an exact deviant count. The
acceptance window is `[nDeviants - maxDevDiff, nDeviants + maxDevDiff]`
with `maxDevDiff = 5` (hardcoded in `mmn_design.py`).

This breaks for blocks longer than ~3 min because the expected
deviant count (`n_tones / (mean_distance + 1) ≈ n_tones / 6`) falls
below the window's lower bound and the loop never terminates.

## Workaround in place

The window is now scaled with `n_tones` (commit `331468c`):
`scaled_diff = max(design.max_dev_diff, round(n_tones * 0.025))`.
This guarantees termination but the deviant count is approximate
(~17.5% instead of the targeted 20% for 4-min blocks).

## TODO

Replace the rejection-sampling algorithm with a cleaner approach.
Candidate options (see prior discussion):

- **A**: Sample distances one at a time, stop at exact target count
- **B**: Inverse-CDF sampling from a target gap distribution
- **D**: Truncated-exponential Poisson process — cleanest model

Decide which to use, implement, and test against current behaviour.
Keep the same public API of `generate_block_sequence()`.

## Notes

- The same `MmnDesign.tone_duration` / `isi_duration` dataclass defaults
  are still 70 ms / 430 ms even though `stimgen/laser/config.py` defines
  `MMN_TONE_DURATION_MS = 50` / `MMN_ISI_DURATION_MS = 400`. The patch
  in `generate_mmn_blocks.py` sets these as class attributes, which
  dataclass instances don't read. Either move to explicit params or
  document the design defaults as authoritative.
