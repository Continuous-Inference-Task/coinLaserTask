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
            self._port = parallel.ParallelPort(address=config.parallel_address)
            logging.exp(
                f"Opened parallel trigger port {config.parallel_address:#x}"
            )

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