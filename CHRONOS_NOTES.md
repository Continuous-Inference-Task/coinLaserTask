# Internal Lab Notes: PST Chronos (PST-100430)

*Note: This information is specific to our internal lab setup and does not apply to general users of this repository.*

The lab uses a PST Chronos (PST-100430) connected to a TMSi SAGA, rather than a standard BrainVision TriggerBox. 

**The Chronos is a USB HID/bulk device — it does NOT present as a standard serial (COM) port.** The current `serial` mode code in `laserTask/triggers.py` (which uses a 4-byte `"m", "h", chr(code), chr(0)` protocol) is completely incompatible with the Chronos.

The Chronos has 16 digital outputs accessible via the I/O Expander or Auxiliary I/O Breakout Cable. In E-Prime, these are controlled via proprietary drivers (`ChronosDigitalOut.WriteByte(value)`). 

From Python/PsychoPy, the options to fix this are:

**Option A (Hardware Fix — Recommended)**
Connect a simple USB-to-serial TTL adapter (FTDI cable, Arduino, or actual BrainVision TriggerBox) between the stimulus PC and the TMSi SAGA's trigger port, bypassing the Chronos entirely for triggers. The current `serial` code would then work with the appropriate byte protocol.

**Option B (Software Fix — LSL)**
If the TMSi SAGA software supports Lab Streaming Layer (LSL), bypass physical trigger cables entirely. Set the task to `lsl` mode, and configure the TMSi recording software to listen for the `LaserTask_Triggers` stream over the network.

**Option C (Software Fix — `psychopy-chronos`)**
Use the `psychopy-chronos` package (pip install). It communicates via `libusb` (VID=0x2266, PID=0x0007, EP 0x01/0x81). Currently, it supports button events + LED control but NOT digital output. To add digital-out support, we would need to reverse-engineer the USB command protocol for `ChronosDigitalOut` from an E-Prime USB trace.

**Option D (Software Fix — Custom Driver)**
Add a dedicated `"chronos"` trigger_mode that opens the Chronos via `libusb`/`pyusb`, sends the init sequence (136 packets), and writes digital-out commands. This requires the Chronos digital-out USB protocol to be documented or captured.
