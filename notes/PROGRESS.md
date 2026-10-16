# PROGRESS

## Current milestone
**M0 — Project setup.** Questions answered on 2026-10-16. Model switched to Sonnet. Waiting for the user to say start (phone app DroidCam to be installed tonight at home).

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
- Nothing yet. Already present and checked 2026-10-16: Vivado + Vitis 2025.1 (`C:\Xilinx\2025.1`), Python 3.13.15, git 2.55.0, GitHub CLI logged in as `alvinhdr`.

## What works
Nothing yet in this project. The previous project (`C:\Users\User\Documents\the assistant Code\FPGA Edge AI Video`) has a working, timing-closed HDMI pipeline to reuse (PLAN.md section 4). All 37 reuse files checked present on 2026-10-16; submodule at `f4613ff`.

## Decisions made
- 2026-10-12: project idea, phone-as-webcam camera, Python viewer first then C# WPF after the board is returned, progressive plan.
- 2026-10-16: board return date 22 Oct → short schedule above (proposed).

## Open problems
- Accuracy reference: a 1 mm ruler is coarse. Plan: measure 10 identical parts in a row and divide by 10; put the ruler in the camera view for calibration. A cheap digital caliper would make the accuracy result stronger (user to decide).
- Warm lamp + shiny metal parts may give reflections; test in M1 before choosing parts.

## Next step
User confirms the short schedule and the parts/caliper questions → switch to Sonnet / medium → M0 setup (git init, submodule, copy reuse files, venv, pass-through build).
