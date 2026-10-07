import sys
from typing import List, Optional

from psychopy import visual, logging
if sys.platform == "win32":
    from psychopy import sound

from laserTask.config import ExperimentConfig, TRIGGER_CODES
from laserTask.triggers import TriggerManager

if sys.platform != "win32":
    import numpy as np
    import sounddevice as sd

    class SimpleTone:
        def __init__(self, freq, secs, volume):
            self.secs = secs
            self.volume = volume
            
            sample_rate = 44100
            t = np.linspace(0, secs, int(sample_rate * secs), False)
            tone = np.sin(freq * t * 2 * np.pi)
            
            # Apply Hanning apodization (5ms ramp at start/end) like PsychoPy's sound
            hwSize = int(min(sample_rate // 200, len(tone) // 15))
            if hwSize > 0:
                hanningWindow = np.hanning(2 * hwSize + 1)
                tone = tone.copy()
                tone[:hwSize] *= hanningWindow[:hwSize]
                tone[-hwSize:] *= hanningWindow[hwSize + 1:]
            
            mono = tone.astype(np.float32)
            self.base_waveform = np.column_stack((mono, mono))
            self.waveform = self.base_waveform * volume
            self.volume = volume

        def play(self):
            sd.play(self.waveform, samplerate=44100)

        def stop(self):
            sd.stop()

        def setVolume(self, vol):
            self.waveform = self.base_waveform * vol
            self.volume = vol

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
        self.win = win
        self.trigger_mgr = trigger_manager
        if not self.enabled:
            logging.exp("Audio stimulation DISABLED")
            return

        logging.exp("Audio stimulation ENABLED")
        if sys.platform == "win32":
            self.tone_standard = sound.Sound(
                config.tone_freq_standard,
                secs=config.tone_duration_standard,
                stereo=True, hamming=True,
                syncToWin=self.win, name="tone_standard",
            )
            self.tone_standard.setVolume(config.tone_volume)

            self.tone_deviant = sound.Sound(
                config.tone_freq_deviant,
                secs=config.tone_duration_deviant,
                stereo=True, hamming=True,
                syncToWin=self.win, name="tone_deviant",
            )
            self.tone_deviant.setVolume(config.tone_volume)
        else:
            self.tone_standard = SimpleTone(
                config.tone_freq_standard,
                secs=config.tone_duration_standard,
                volume=config.tone_volume,
            )
            self.tone_deviant = SimpleTone(
                config.tone_freq_deviant,
                secs=config.tone_duration_deviant,
                volume=config.tone_volume,
            )

        self._reset()

    # --------------------------------------------------------------------- #
    def _reset(self):
        self.current_trigger = 0
        self.frame_ctr = 0
        self.tone_idx = 0
        self._cur_id: Optional[str] = None
        self._next_onset = 0
        self._block_frames: Optional[int] = None
        self.sequence: List[str] = []
        self.onsets: List[int] = []
        self.isis: List[int] = []
    # --------------------------------------------------------------------- #
    def _get_soa_frames(self) -> int:
        """Return the stimulus-onset asynchrony (SOA) in frames.

        SOA is the duration from one tone onset to the next tone onset.
        For frequency MMN, SOA = tone_frames + tone_isi_frames.
        For duration MMN, SOA = standard_tone_frames + base_isi_frames,
        which remains constant across standard and deviant tones.
        """
        fps = self.cfg.target_refresh_rate
        std_dur = (
            self.cfg.tone_duration_standard
            if self.cfg.tone_duration_standard > 0
            else self.cfg.tone_duration
        )
        std_frames = int(round(std_dur * fps))
        return std_frames + self.cfg.tone_isi_frames

    # --------------------------------------------------------------------- #
    def load_block_sequence(
        self, filepath: str, n_block_frames: Optional[int] = None
    ) -> None:
        """Read tone-identity sequence (``"1"`` / ``"2"``) from *filepath*."""
        if not self.enabled:
            return
        self._reset()
        raw_tokens: List[str] = []
        with open(filepath, "r") as fh:
            for line in fh:
                token = line.strip().split(",")[0].strip()
                if token:
                    raw_tokens.append(token)
        # Skip header row if present (e.g. "toneType" or any non-numeric label)
        if raw_tokens and raw_tokens[0] not in {"1", "2"}:
            raw_tokens = raw_tokens[1:]
        # Filter for valid tone identities; warn if any invalid entry found
        valid_sequence: List[str] = []
        for t in raw_tokens:
            if t in {"1", "2"}:
                valid_sequence.append(t)
            else:
                logging.warning(
                    f"Audio sequence: ignoring invalid tone identifier '{t}' in {filepath}"
                )
        self.sequence = valid_sequence
        self.tone_idx = 0
        if len(self.sequence) > 0:
            self._cur_id = self.sequence[self.tone_idx]
            soa = self._get_soa_frames()
            n_tones = len(self.sequence)
            max_std_frames = int(
                round(
                    max(
                        self.cfg.tone_duration_standard,
                        self.cfg.tone_duration_deviant,
                    )
                    * self.cfg.target_refresh_rate
                )
            )
            total_span = (n_tones - 1) * soa + max_std_frames
            if n_block_frames is None:
                n_block_frames = 14400
                logging.warning(
                    "Audio schedule: block length unknown, assuming 14400 frames."
                )
            self._block_frames = n_block_frames
            if n_block_frames - total_span < 1:
                logging.error(
                    f"Audio schedule cannot fit {n_tones} tones (needs {total_span} frames, "
                    f"block has {n_block_frames}). Clamping first onset to frame 1; last tone(s) will be truncated."
                )
                latest_first_onset = 1
            else:
                latest_first_onset = max(1, n_block_frames - total_span)
            self._next_onset = min(self.cfg.tone_isi_frames, latest_first_onset)

    # --------------------------------------------------------------------- #
    def update_frame(self) -> int:
        """Advance the tone state machine by one frame.

        Returns
        -------
        int
            Trigger code emitted this frame (0 if none).
        """
        if not self.enabled or not self.sequence or self._cur_id is None:
            return 0

        self.frame_ctr += 1
        self.current_trigger = 0

        # When the scheduled onset frame is reached, play and trigger the next tone
        if self._cur_id is not None and self.frame_ctr >= self._next_onset:
            self._play()
            soa = self._get_soa_frames()
            self.isis.append(soa)
            self._next_onset = self.frame_ctr + soa

        return self.current_trigger

    # --------------------------------------------------------------------- #
    def _play(self):
        tone = self.tone_standard if self._cur_id == "1" else self.tone_deviant
        if sys.platform == "win32":
            tone.play()  # sound.Sound(syncToWin=win) defers onset to the next flip
        else:
            self.win.callOnFlip(tone.play)
        self.current_trigger = (
            TRIGGER_CODES["tone_standard"]
            if self._cur_id == "1"
            else TRIGGER_CODES["tone_deviant"]
        )
        self.onsets.append(self.frame_ctr)
        self.tone_idx += 1
        if self.tone_idx < len(self.sequence):
            self._cur_id = self.sequence[self.tone_idx]
        else:
            self._cur_id = None

    # --------------------------------------------------------------------- #
    def stop(self):
        """Stop any currently playing tone."""
        if not self.enabled:
            return
        self.tone_standard.stop()
        self.tone_deviant.stop()