# B1 — first board session (camera + pass-through check)

Goal: see the camera picture on the TV through the Zybo, with the green window frame drawn on it.
Needs: the M0 build (`build/inspect.bit`, timing met: WNS +1.163 ns). No ARM program needed.
Length: 30–60 min. Record the start/end time in `notes/PROGRESS.md` (board hours used).

## Before (prepared in advance)
- [x] Bitstream built from commit `a7b905a` (tag `m0-done`), timing met.
- [x] `py/capture_frames.py` ready (laptop webcam = camera 0 works).

## Setup you do (physical)
1. Phone in the stand, looking straight DOWN at the table, about 12–20 cm above. The bolts will be only 50–100 pixels long, so closer is better.
2. Black desk mat as background. Lamp from the SIDE, low, so the shiny bolts do not make big white spots. Try the lamp on the left, then on the right.
3. Phone: start DroidCam (Wi-Fi mode or USB). Laptop: DroidCam Client (see the notes), or a browser with the address shown on the phone.
4. Laptop display: **Duplicate**, **1280×720, 60 Hz**. Camera picture full screen. Do-not-disturb ON.
5. Cables: laptop HDMI out → Zybo **HDMI RX** (J1). Zybo **HDMI TX** (J2) → TV. Board power jumper on USB, boot jumper on **JTAG**. USB cable to the laptop. Switches sw[0], sw[1] down.
6. Power the board on.

## Program (tell the assistant "board is connected")
```
& "C:\Xilinx\2025.1\Vivado\bin\xsdb.bat" scripts/program.tcl bit
```
(If `ps7_init` fails right after power-on, run it again.)

## Check (look at the TV and the board)
- [ ] LD1 (led[1]) on = 200 MHz clock locked; LD2 (led[2]) on = HDMI input locked; led[3] blinks.
- [ ] TV shows the camera picture, no flicker, same colours.
- [ ] A green square frame in the middle of the picture. sw[0] up = gray picture. sw[1] up = frame hidden.
- [ ] Put one bolt inside the frame: is it sharp and clear? Photo of the TV.

## Record (very important, the board goes back on 22 Oct)
- 3 photos of the TV (bolt on black mat, lamp left / lamp right, nut).
- Write the setup: phone height in cm, lamp position, DroidCam resolution, laptop settings.
- If the picture is blurry or has a colour problem: photo + tell the assistant, do not fix by guessing.

## After
The assistant writes: hours used, what worked, problems, in `notes/PROGRESS.md`.
