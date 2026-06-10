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

## 3. LSL (Lab Streaming Layer) Setup

LSL mode pushes event markers over the network to LabRecorder (or any LSL inlet). This is the recommended setup for modern EEG systems that support LSL natively.

### Stream Properties
| Property | Value | Meaning |
|----------|-------|---------|
| Name | `LaserTask_Triggers` | How the stream appears in LabRecorder |
| Type | `Markers` | Standard LSL marker stream type |
| Channel count | `1` | One marker per sample |
| Nominal rate | `0` | Irregular stream (no fixed sampling rate) |
| Format | `int32` | Integer trigger codes — matches `TRIGGER_CODES` exactly |
| Source ID | `laser_task_triggers` | Unique stream identifier |

**Why `int32` instead of `string`?**  
Some guides recommend `string` for human readability. We keep `int32` because:
- The analysis pipeline already works with integer codes.
- `int32` is transmitted and parsed identically reliably.
- It avoids string↔int conversion in analysis scripts.

### LSL Best Practices
1. **Create the outlet BEFORE starting LabRecorder.** The stream must exist when you click "Start Recording." Our code creates the `StreamOutlet` right after the dialog/window opens, well before any trial events.
2. **Keep the outlet alive for the entire experiment.** The `TriggerManager` holds the outlet as an instance attribute from creation until `close()` is called.
3. **Stop LabRecorder before the stream dies.** After the final reward screen, a **stop-recording screen** appears that holds the experiment open. The experimenter must stop the recording in LabRecorder and then press **RETURN** to close the task. This prevents the LSL stream from vanishing while LabRecorder is still writing.

---

## 4. Trigger Timing & Synchronization

### Visual Triggers — Frame-Synced via `callOnFlip()`

Visual event markers (laser onset, key presses, shield size changes) are sent using PsychoPy's `win.callOnFlip()`. This guarantees that the LSL/hardware timestamp is coincident with the actual buffer swap — the exact moment the stimulus appears on screen.

**Why this matters:** Without `callOnFlip`, the trigger is sent *after* `win.flip()` returns. On a 60 Hz monitor that introduces a systematic ~1 ms offset. For high-precision ERP/MEG analysis, frame-synced triggers remove that offset.

The relevant code in `laserTask/experiment.py`:

```python
# Compute triggers earlier in the frame loop...
# ... then register them before flip:
if partial_release_trig:
    win.callOnFlip(trig.send, partial_release_trig)
if size_trig_val:
    win.callOnFlip(trig.send, size_trig_val)
if do_send:
    win.callOnFlip(trig.send, trig_val)

cur_frame += 1
win.flip()   # all registered callbacks fire at the exact swap instant
```

If multiple triggers fire in the same frame, they are sent in a rapid burst during the vertical blanking interval, in the same order as the original post-flip logic.

### Audio Triggers — Synced to Audio Onset, NOT Display

Background tone markers (standard/deviant in the MMN oddball) are sent **immediately** when the tone `.play()` method is called. They are **not** routed through `callOnFlip()`.

**Why?** Audio runs on a different clock than the display. On Linux/macOS, `sounddevice` starts playback immediately when `.play()` returns — delaying the marker to the next flip would make timing *worse*. On Windows with PTB, `syncToWin=True` queues the tone to the next flip, but the audio engine's internal buffering is already sub-millisecond tight. Sending the trigger next to `.play()` is the closest possible timestamp to the actual acoustic onset on every platform.

| Trigger Type | Sync Method | File |
|--------------|-------------|------|
| Laser hit/miss, key presses, shield size | `win.callOnFlip(trig.send, code)` | `experiment.py` |
| Tone standard/deviant | Immediate inside `audio.py` `_play()` | `audio.py` |
| Block/experiment start/end | Immediate (not frame-synced, events are long-duration) | `experiment.py` |
| `last_frame` | Immediate (no subsequent flip to sync to) | `experiment.py` |

---

## 5. Customizing Event Marker Codes

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

## 6. Experiment Workflow with Recording Hardware

Typical session flow for the experimenter:

1. **Start LabRecorder** and verify the `LaserTask_Triggers` stream is visible.
2. **Click "Start Recording"** in LabRecorder.
3. **Launch the experiment** (`python bootstrap.py` or `python laserTask/experiment.py`).
4. The participant completes the task. The `exp_start`, block, and trial triggers are recorded automatically.
5. After the final reward screen, a **stop-recording screen** appears:
   > "Experimenter: Please stop the recording in LabRecorder now. Press RETURN to close the experiment once recording is stopped."
6. **Click "Stop Recording"** in LabRecorder.
7. **Press RETURN** to close the experiment and release the LSL outlet.

---

## Troubleshooting

- **Linux Parallel Port Permission Denied:** Run `sudo usermod -a -G lp $USER` (and log out/in) to grant your user account access to `/dev/parport0`.
- **Linux Serial Port Permission Denied:** Run `sudo usermod -a -G dialout $USER`.
- **Task crashes immediately on start:** If the port address is wrong, PsychoPy will crash when trying to open the connection. Run `python bootstrap.py` and set the trigger mode to `dummy` to test if the port configuration is the cause.
- **LabRecorder doesn't see the stream:** Make sure the experiment PC and the EEG acquisition PC are on the same local network segment. LSL uses multicast ports 16571–16581, which must not be blocked by a firewall.
- **LSL markers have the wrong timestamp:** If you modified the code, double-check that visual triggers use `callOnFlip()` and audio triggers do not. Reversing this will desynchronize the event markers.
