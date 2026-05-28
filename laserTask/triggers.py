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
            # -------------------------------------------------------------------
            # HARDWARE NOTE — the lab uses a PST Chronos (PST-100430), NOT a
            # BrainVision TriggerBox.  Chronos is a USB HID/bulk device — it does
            # NOT present as a serial (COM) port.  The current serial-mode code
            # (4-byte "m", "h", chr(code), chr(0) protocol) is therefore
            # incompatible with the lab's actual hardware.
            #
            # The Chronos has 16 digital outputs accessible via the I/O Expander
            # or Auxiliary I/O Breakout Cable.  In E-Prime these are controlled via
            # ChronosDigitalOut.WriteByte(value).  From Python, the options are:
            #
            #   Option A — use the `psychopy-chronos` package (pip install).
            #   It communicates via libusb (VID=0x2266, PID=0x0007, EP 0x01/0x81).
            #   Currently supports button events + LED control but NOT digital
            #   output.  To add digital-out support, we need the USB command
            #   protocol for ChronosDigitalOut — likely a vendor-specific control
            #   or bulk transfer.  This could be reverse-engineered from an
            #   E-Prime USB trace.
            #
            #   Option B — connect a simple USB-to-serial adapter (FTDI cable,
            #   Arduino, or BrainVision TriggerBox) between the stimulus PC and
            #   the EEG/MEG amplifier's trigger port.  The current serial code
            #   would then work with the appropriate byte protocol (typically a
            #   single byte for most trigger interfaces).
            #
            #   Option C — add a dedicated "chronos" trigger_mode that opens the
            #   Chronos via libusb/pyusb, sends the init sequence (136 packets),
            #   and writes digital-out commands.  This requires the Chronos
            #   digital-out USB protocol to be documented or captured.
            #
            # TODO: decide which option to implement and verify with the lab.
            #   - Option B is the fastest path if a USB-serial adapter is available.
            #   - Option A/C requires protocol work but gives direct Chronos control.
            #
            # -------------------------------------------------------------------
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