from laserTask.config import ExperimentConfig
import logging

from psychopy import core, logging


class TriggerManager:
    """Send event markers to external recording hardware.

    Abstracts over serial / parallel / LSL / dummy backends so the
    experiment code never needs to know which one is active.

    Parameters
    ----------
    config : ExperimentConfig

    Examples
    --------
    >>> cfg = ExperimentConfig(trigger_mode="serial", serial_port="COM6")
    >>> trig = TriggerManager(cfg)
    >>> trig.send(TRIGGER_CODES["exp_start"])
    >>> trig.close()
    """

    def __init__(self, config: ExperimentConfig):
        self.mode = config.trigger_mode
        self._port = None
        self._outlet = None

        if self.mode == "serial":
            import serial
            self._port = serial.Serial(
                config.serial_port,
                config.serial_baud_rate,
                timeout=config.serial_timeout,
            )
            logging.exp(f"Opened serial trigger port {config.serial_port}")

        elif self.mode == "parallel":
            from psychopy import parallel
            addr = config.parallel_address
            if isinstance(addr, str):
                addr_str = addr.strip()
                if addr_str.lower().startswith("0x"):
                    try:
                        addr = int(addr_str, 16)
                    except ValueError:
                        pass
                else:
                    try:
                        addr = int(addr_str)
                    except ValueError:
                        pass
            self._port = parallel.ParallelPort(address=addr)
            if isinstance(addr, int):
                logging.exp(f"Opened parallel trigger port {addr:#x}")
            else:
                logging.exp(f"Opened parallel trigger port {addr}")

        elif self.mode == "lsl":
            import pylsl
            info = pylsl.StreamInfo(
                "LaserTask_Triggers", "Markers", 1, 0, "int32",
                "laser_task_triggers",
            )
            self._outlet = pylsl.StreamOutlet(info)
            logging.exp("Created LSL trigger outlet")

        elif self.mode == "dummy":
            logging.exp("TriggerManager in dummy mode (console only)")

        else:
            raise ValueError(
                f"Unknown trigger_mode '{self.mode}'. "
                "Choose from: 'serial', 'parallel', 'lsl', 'dummy'."
            )

    # --------------------------------------------------------------------- #
    def send(self, code: int) -> None:
        """Send a single trigger *code* (int, typically 1–127)."""
        if self.mode == "serial":
            # Current implementation sends 4 bytes: "m", "h", chr(code), chr(0).
            # This may be a protocol for older BrainAmp hardware or a non-TriggerBox
            # serial device.  The standard BrainVision TriggerBox (rev.02 and Plus)
            # protocol expects a *single byte* — just the code value.
            #
            # TODO: verify with the lab what serial trigger hardware is used.
            # If it's a standard BrainVision TriggerBox, replace with:
            #
            #   self._port.write(bytes([code]))
            #   self._port.flush()
            #
            # HOW TO TEST:
            #   1. Connect the trigger hardware to the MEG/EEG recording PC.
            #   2. Run in dummy mode first: `python -c "
            #      from laserTask.triggers import TriggerManager
            #      from laserTask.config import ExperimentConfig
            #      cfg = ExperimentConfig(trigger_mode='dummy')
            #      trig = TriggerManager(cfg)
            #      trig.send(30)  # should print '[TRIGGER] 30'
            #      trig.close()"`
            #   3. Switch to serial mode with the correct port/baud rate.
            #   4. Send a known code (e.g., 30) and check BrainVision Recorder:
            #      - With current 4-byte protocol: look for markers S 109, S 104, S 30
            #        appearing in sequence.  If it works, the lab's hardware expects this.
            #      - With single-byte protocol: BrainVision Recorder should show
            #        exactly one marker "S 30" at the expected baud rate.
            #   5. Send code 0 to verify the reset/pulse boundary works.
            for ch in ("m", "h", chr(code), chr(0)):
                self._port.write(ch.encode())
            self._port.flush()

        elif self.mode == "parallel":
            self._port.setData(code)
            core.wait(0.002)
            self._port.setData(0)

        elif self.mode == "lsl":
            self._outlet.push_sample([code])

        else:  # dummy
            print(f"[TRIGGER] {code}")

    # --------------------------------------------------------------------- #
    def close(self) -> None:
        """Release hardware resources."""
        if self._port is not None and self.mode == "serial":
            self._port.close()
            logging.exp("Serial trigger port closed")