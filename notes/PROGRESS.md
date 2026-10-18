# PROGRESS

## Current milestone
**M0 done (2026-10-16), tagged `m0-done`.** Next: **M1 - camera setup and data capture** (needs the user at home: DroidCam on the phone, stand, lamp, bolts, black paper/cloth). Board return: 2026-10-22.

## Board time
- Board: Digilent Zybo Z7-10 (borrowed). **Return date: Thursday 2026-10-22** (user, 2026-10-16). Board sessions must happen 16–21 Oct.
- Board hours used: 0. Board sessions done: none.
- Old project's SD card (Edge AI BOOT.bin): user still has it somewhere, will look for it. Not needed for B1 if the M0 pass-through build is programmed over JTAG.

## Order of work (by milestone, no fixed days; board returns 2026-10-22)
User has no fixed daily schedule, so work goes milestone by milestone, as fast as possible. Order: M0 setup -> M1 camera + frames -> B1 (short board check) -> M2 spec + golden model + OpenCV -> M3+M4 merged (RTL core + window overlay, bit-exact sims, full build) -> M5 ARM app -> B2 first live measurement -> M6.1 text overlay -> B3 evidence -> final build -> B4 demo + video -> return board by 22 Oct.
Otsu/histogram and 3x3 filter only if time is left; otherwise build later and prove in simulation on recorded frames. Python viewer and C# WPF app after the board is returned (replay of recorded logs). Ask the user before each board session how many hours they have.

## Answers from the user (2026-10-16)
- Repo `fpga-vision-inspection`, private, GitHub `alvinhdr`: yes, the assistant may create it with `gh`.
- Parts: no coins. Has **many identical bolts/screws** (use lying flat: length + angle), maybe nuts/washers. Test candidates with camera in M1; prefer dark/matte (yellow lamp may reflect on shiny).
- Measuring tool: only a **30 cm ruler** (1 mm marks). No caliper (yet).
- Phone: **Android**, no webcam app installed yet. Laptop has a built-in webcam (fallback).
- Lighting/setup: desk lamp with **yellowish (warm) light**, white paper; phone stand probably available, otherwise a box/books.
- Python venv + packages: allowed. User wants a note of everything installed (section below).
- Tools: user allows free use of tools/installs (standing permission), but every install must be reported and written down.

## Installed software (this project)
- Already present, checked 2026-10-16: Vivado + Vitis 2025.1 (`C:\Xilinx\2025.1`), Python 3.13.15, git 2.55.0, GitHub CLI logged in as `alvinhdr`.
- Installed 2026-10-16 (Python venv `.venv/` inside the repo folder, git-ignored; source PyPI; list in `py/requirements.txt`): `numpy 2.5.4` (arrays, golden model), `opencv-python 5.0.0.93` (cross-check, camera capture), `pillow 12.3.0` (PNG files), `pyserial 3.5` (UART), `mss 10.2.0` (screen capture).
- Git submodule `third_party/vivado-library` (Digilent HDMI IP, GitHub, pinned `f4613ff`).
- Still to install, only after asking: .NET SDK + Visual Studio / VS Code (C# phase).

## What works
- **M0 build (pass-through top, commit after 1a7dd4f):** full Vivado build in about 5 min. Timing met: WNS +1.163 ns, WHS +0.033 ns, 0 failing endpoints. Resources: 1,071 LUT (6.1 %), 1,210 FF (3.4 %), 0 BRAM, 0 DSP. Method: `build_hw.tcl all`, numbers from `build/reports/`. NOT yet tested on the board (B1 will do that).
Nothing yet in this project. The previous project (`C:\Users\User\Documents\the assistant Code\FPGA Edge AI Video`) has a working, timing-closed HDMI pipeline to reuse (PLAN.md section 4). All 37 reuse files checked present on 2026-10-16; submodule at `f4613ff`.

## Decisions made
- 2026-10-16: user wants AI in the project. Decision: the measuring core stays classic (exact numbers). An AI layer is added AFTER the MVP works, as an extra: a small model that classifies good/bad from the part's shape/features (trained on the recorded frames, runs on the PC or ARM first, compared with the plain tolerance rule). Exact design to be agreed with the user at the start of M2 (not before). Do not let it delay the board milestones.
- 2026-10-12: project idea, phone-as-webcam camera, Python viewer first then C# WPF after the board is returned, progressive plan.
- 2026-10-16: board return date 22 Oct → short schedule above (proposed).

## M1 facts (2026-10-18)
- Parts: **bolts about 10 mm long, nuts about 5 mm** (very small). Shiny silver. Background: black desk mat (good: bright metal on dark).
- Consequence for the design: the object is BRIGHTER than the background -> the threshold block needs a polarity bit (object if gray > T, or gray < T). Put it in `docs/MEASUREMENT.md` (M2) and in the register map.
- Resolution: field of view must be small. At 25 cm wide view, 1 px = 0.2 mm -> bolt = 50 px, nut = 25 px (error +-1 px = 2 % and 4 %). Camera 12-15 cm above (view about 12-15 cm wide, 1 px about 0.1 mm) is much better. Ruler checks only to about 0.5 mm at this size -> accuracy claims must say so; a digital caliper would help.
- `py/capture_frames.py` written and checked: laptop webcam is camera 0 (1280x720). DroidCam on the phone is installed, phone stand available.
- The old SD card is not at hand (left at the other place): not needed, B1 uses JTAG.
- Date check: today 2026-10-18; board returns 2026-10-22 (4 days). B1 checklist: `notes/B1_CHECKLIST.md`.

## Open problems
- Accuracy reference: a 1 mm ruler is coarse. Plan: measure 10 identical parts in a row and divide by 10; put the ruler in the camera view for calibration. A cheap digital caliper would make the accuracy result stronger (user to decide).
- Warm lamp + shiny metal parts may give reflections; test in M1 before choosing parts.

## Next step
M1 (Sonnet / medium). Before it: user installs DroidCam on the phone, finds stand, bolt length in mm, black paper/cloth, old SD card. Then the assistant writes `py/capture_frames.py` and a B1 checklist (program pass-through over JTAG: `xsdb scripts/program.tcl bit`).
