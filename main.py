# main.py
from laserTask.config import ExperimentConfig
from laserTask.experiment import run_experiment
from laserTask.shield import ShieldSizeConfig

# NOTE: See README.md for full documentation.
# Key config files:
#   - stimgen/laser/config.py    (laser sequence generation parameters)
#   - laserTask/config.py         (experiment runtime settings)
#
# NOTE: prior to running:
# adjust machine-specific config values for monitor_name, screen_index,
# run-mode specific: fullscreen, trigger_mode, enable_audio,
# experiment design: shield_degrees, loss_factor, n_blocks
# NOTE: for shield-adjustments, need to import and adapt ShieldSizeConfig object

# NOTE: small-ish things
    # TODO: add reward function as argument, allowing for custom implementations
    # TODO: move rotation_speed and circle_radius controls to shieldconfig-thingy
    # TODO: warning when laser duration is low

# NOTE: bigger-ish things
    # TODO: carefully check reward structure in reward.py to make sure it matches expectations (on that NOTE: check expectations with Lilian)
    # TODO: triggers for shield size adjustments --> box? make that channels 3,4 or sth
    # TODO: practice mode 
    # TODO: refresh rate (Felix)

# NOTE: after testing is over
    # TODO: remove data/ from gitignore once finished testing?
    # TODO: toggle fullscreen and window size, trigger_mode, etc.
    
# TODO: add other stimuli / sequences to have a test run 


if __name__ == "__main__":
    cfg = ExperimentConfig(
        enable_audio=True,
        input_device="keyboard",  # toggle keyboard or response_box to change instruction text accordingly
        trigger_mode="dummy",
        # fullscreen=False, # NOTE: not fullscreen for testing
        # window_size=(800, 600), # NOTE: not fullscreen for testing
        monitor_name="testMonitor",  # lilianMac does not exist on other devices
        key_left="d",
        key_right="k",
        allow_shield_adjustment=False,  # NOTE: fixed 20 deg shield for PEDUKS replication
        tone_isi_frames=26,  # NOTE: 26 frames = ~433 ms at 60 Hz (PEDUKS original: 430 ms ISI)
        # shield_sizes=ShieldSizeConfig.adjustable_standard()
    )
    run_experiment(cfg)
