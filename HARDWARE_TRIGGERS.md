# Hardware Triggers & EEG/MEG Setup

Because every research lab has a unique hardware setup for recording physiological data (EEG, MEG, etc.), getting triggers to talk to your specific system can often be quite tricky and require some trial and error.

This guide aims to support you in connecting the task to your hardware and explain how you might customize the event markers (trigger codes) sent to your data.

---

## 1. Setting the Connection Type

The experiment supports four ways of sending triggers. You can configure this interactively using the setup wizard (`python bootstrap.py`), or by editing `laserTask/config.json` directly.

- **`parallel`**: Sends standard 8-bit TTL pulses over a parallel port (LPT port). Common for older EEG setups.
- **`serial`**: Sends byte markers over a USB-to-Serial connection (e.g., to a BrainVision TriggerBox).
- **`lsl`**: Pushes markers to a Lab Streaming Layer (LSL) outlet named `LaserTask_Triggers`. Useful for network-based synchronization.
- **`dummy`**: Prints triggers to the console instead of hardware. (Useful for testing the task on your personal laptop without crashing).

---

## 2. Configuring the Port Address

If you are using `parallel` or `serial` mode, you must tell PsychoPy where the hardware port is located. Set these in the setup wizard or `config.json`.

### Parallel Port Address (`parallel_address`)
- **Linux**: Usually `"/dev/parport0"`. *(Note: Your user must be in the `lp` group to access this port).*
- **Windows**: Usually a memory address like `"0x0378"`, `"0x03BC"`, or `"0xD010"` depending on your PCIe card. You can find this in the Windows Device Manager under the port's "Resources" tab.
- **macOS**: Parallel ports are generally unsupported on Mac.

### Serial Port Address (`serial_port`)
- **Linux**: Usually `"/dev/ttyUSB0"` or `"/dev/ttyACM0"`.
- **Windows**: Usually `"COM3"`, `"COM4"`, etc. (Check Device Manager).
- **macOS**: Usually `"/dev/cu.usbserial-XXXX"`.

You may also need to adjust `serial_baud_rate` (default `115200`) depending on what your specific trigger box expects.

---

## 3. Customizing Event Marker Codes

The actual numbers sent to your EEG/MEG system (the markers) are **not** stored in `config.json`. They are hardcoded in the Python code so they remain consistent across all participants.

If your lab's analysis pipeline requires specific marker values (for example, if `10` is already used for something else), you must edit the code directly:

1. Open `laserTask/config.py` in a text editor.
2. Scroll to the bottom to find the `TRIGGER_CODES` dictionary.
3. Change the integer values to match your lab's requirements:

```python
TRIGGER_CODES: Dict[str, int] = {
    "exp_start":   100,
    "block_start":  80,
    "laser_hit":    10,   # Change these numbers...
    "laser_miss":   20,   # ...to fit your lab's marker scheme
    # ...
}
```

*Note: The values must be integers between 1 and 255 if you are using a parallel port.*

---

## Troubleshooting

- **Linux Parallel Port Permission Denied:** Run `sudo usermod -a -G lp $USER` (and log out/in) to grant your user account access to `/dev/parport0`.
- **Linux Serial Port Permission Denied:** Run `sudo usermod -a -G dialout $USER`.
- **Task crashes immediately on start:** If the port address is wrong, PsychoPy will crash when trying to open the connection. Run `python bootstrap.py` and set the trigger mode to `dummy` to test if the port configuration is the cause.
