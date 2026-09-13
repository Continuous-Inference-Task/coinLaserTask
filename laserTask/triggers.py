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
    >>> from laserTask.config import get_config
    >>> cfg = get_config()
    >>> trig = TriggerManager(cfg)
    >>> trig.send(TRIGGER_CODES["exp_start"])
    >>> trig.close()
    """

    def __init__(self, config: ExperimentConfig):
        self.mode = config.trigger_mode
        self._port = None
        self._outlet = None

        if self.mode == "serial":
            try:
                import serial
                self._port = serial.Serial(
                    config.serial_port,
                    config.serial_baud_rate,
                    timeout=config.serial_timeout,
                )
                logging.exp(f"Opened serial trigger port {config.serial_port}")
            except Exception as exc:
                logging.error(
                    f"Could not open serial trigger port '{config.serial_port}': {exc}. "
                    "Falling back to dummy trigger mode."
                )
                print(f"\n  ⚠  WARNING: Serial trigger port initialization failed: {exc}")
                print("     Falling back to DUMMY trigger mode.\n")
                self.mode = "dummy"

        elif self.mode == "parallel":
            try:
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
            except Exception as exc:
                logging.error(
                    f"Could not open parallel trigger port at address '{config.parallel_address}': {exc}. "
                    "Falling back to dummy trigger mode."
                )
                print(f"\n  ⚠  WARNING: Parallel trigger port initialization failed: {exc}")
                print("     Falling back to DUMMY trigger mode.\n")
                self.mode = "dummy"

        elif self.mode == "lsl":
            try:
                import pylsl
                info = pylsl.StreamInfo(
                    "LaserTask_Triggers", "Markers", 1, 0, "int32",
                    "laser_task_triggers",
                )
                self._outlet = pylsl.StreamOutlet(info)
                logging.exp("Created LSL trigger outlet")
            except Exception as exc:
                logging.error(f"Could not open LSL trigger outlet: {exc}.")
                raise RuntimeError(
                    f"Failed to initialize LSL trigger outlet: {exc}. "
                    "Ensure pylsl is installed and network/multicast is available."
                ) from exc

        if self.mode == "dummy":
            logging.exp("TriggerManager in dummy mode (console only)")

        elif self.mode not in ("serial", "parallel", "lsl"):
            raise ValueError(
                f"Unknown trigger_mode '{self.mode}'. "
                "Choose from: 'serial', 'parallel', 'lsl', 'dummy'."
            )

    # --------------------------------------------------------------------- #
    def send(self, code: int) -> None:
        """Send a single trigger *code* (int, typically 1–127)."""
        if self.mode == "serial":
            # Note: Protocol expects BrainVision TriggerBox or compatible adapter
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