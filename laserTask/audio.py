import sys
from typing import List, Optional
from typing import List, Optional

from psychopy import sound, visual, logging

from laserTask.config import ExperimentConfig, TRIGGER_CODES
from laserTask.triggers import TriggerManager

class AudioStimulationManager:
    """Background auditory oddball stimulation (optional).

    Plays a sequence of standard / deviant tones at fixed ISI and sends
    triggers for each onset.  Completely disabled when
    ``config.enable_audio is False``.

    Parameters
    ----------
    config : ExperimentConfig
    win    : visual.Window   – needed for ``syncToWin``
    trigger_manager : TriggerManager
    """

    def __init__(
        self,
        config: ExperimentConfig,
        win: visual.Window,
        trigger_manager: TriggerManager,
    ):
        self.enabled = config.enable_audio
        self.cfg = config
        self.trigger_mgr = trigger_manager

        if not self.enabled:
            logging.exp("Audio stimulation DISABLED")
            return

        logging.exp("Audio stimulation ENABLED")
        self.tone_standard = sound.Sound(
            config.tone_freq_standard,
            secs=config.tone_duration,
            stereo=True, hamming=True,
            syncToWin=True, name="tone_standard",
        )
        self.tone_standard.setVolume(config.tone_volume)

        self.tone_deviant = sound.Sound(
            config.tone_freq_deviant,
            secs=config.tone_duration,
            stereo=True, hamming=True,
            syncToWin=True, name="tone_deviant",
        )
        self.tone_deviant.setVolume(config.tone_volume)

        self._reset()

    # --------------------------------------------------------------------- #
    def _reset(self):
        self.is_playing = False
        self.is_waiting = False
        self.current_trigger = 0
        self.frame_ctr = 0
        self.tone_idx = 0
        self._cur_id: Optional[str] = None
        self._next_onset = 0
        self.sequence: List[str] = []
        self.onsets: List[int] = []
        self.isis: List[int] = []

    # --------------------------------------------------------------------- #
    def load_block_sequence(self, filepath: str) -> None:
        """Read tone-identity sequence (``"1"`` / ``"2"``) from *filepath*."""
        if not self.enabled:
            return
        self._reset()
        with open(filepath, "r") as fh:
            self.sequence = [
                line.strip().split(",")[0].strip() for line in fh
            ]
        self.tone_idx = 1  # index 0 is typically a header / skip
        self._cur_id = self.sequence[self.tone_idx]

    # --------------------------------------------------------------------- #
    def update_frame(self) -> int:
        """Advance the tone state machine by one frame.

        Returns
        -------
        int
            Trigger code emitted this frame (0 if none).
        """
        if not self.enabled:
            return 0
        if not self.sequence or self._cur_id is None:
            return 0

        self.frame_ctr += 1
        self.current_trigger = 0

        if not self.is_playing and not self.is_waiting:
            isi = self.cfg.tone_isi_frames
            self.isis.append(isi)
            self._next_onset = self.frame_ctr + isi
            self.is_waiting = True

        elif not self.is_playing and self.is_waiting:
            if self.frame_ctr >= self._next_onset:
                self._play()

        elif self.is_playing:
            self._check_done()

        return self.current_trigger

    # --------------------------------------------------------------------- #
    def _play(self):
        if self._cur_id not in {"1", "2"}:
            self.is_playing = False
            self.is_waiting = False
            return
        if self._cur_id == "1":
            self.tone_standard.play()
            self.current_trigger = TRIGGER_CODES["tone_standard"]
        elif self._cur_id == "2":
            self.tone_deviant.play()
            self.current_trigger = TRIGGER_CODES["tone_deviant"]
        self.onsets.append(self.frame_ctr)
        self.trigger_mgr.send(self.current_trigger)
        self.is_playing = True
        self.is_waiting = False

    def _check_done(self):
        self.current_trigger = 0
        tone = (
            self.tone_standard if self._cur_id == "1" else self.tone_deviant
        )
        end_frame = (
            self._next_onset
            + tone.secs * self.cfg.target_refresh_rate
            + 3
        )
        if self.frame_ctr >= end_frame:
            tone.stop()
            self.is_playing = False
            self.tone_idx += 1
            if self.tone_idx < len(self.sequence):
                self._cur_id = self.sequence[self.tone_idx]

    # --------------------------------------------------------------------- #
    def stop(self):
        """Stop any currently playing tone."""
        if not self.enabled:
            return
        self.tone_standard.stop()
        self.tone_deviant.stop()
        self.is_playing = False
        self.is_waiting = False