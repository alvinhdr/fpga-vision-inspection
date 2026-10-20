# PROGRESS

## Current milestone
**All board work done (2026-10-20 evening). Board returned 2026-10-21.** M0-M5 + B1 + B2 finished; MVP complete and measured. Remaining (NO board needed): Standard FPGA extras in simulation (Otsu/histogram, text overlay), AI layer, Python viewer, C# WPF app, PLC link (optional), docs/RESULTS.md, README, demo GIF, CV bullets, GitHub Release. Order and details in the next-step list below.

## Board time
- Board: Digilent Zybo Z7-10 (borrowed). **Return date: Thursday 2026-10-22** (user, 2026-10-16). Board sessions must happen 16–21 Oct.
- Board hours used: about 3.1 (B1 about 1.0 h on 2026-10-18; B2 about 2.1 h on 2026-10-20, 19:10-21:15 from commit times and the system clock). Board sessions done: B1, B2 (B3/B4 content was folded into B2). Board returned on 2026-10-21 (last day).
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
- Installed 2026-10-18 via winget: `DroidCam Client (New) 7.2.1` (dev47apps.DroidCamOBSClient, official publisher, installer hash verified) - Windows side of the phone webcam (the phone app waits for it; no browser stream).
- Installed 2026-10-20 (pip, project venv): `scikit-learn 1.9.1` (+ `scipy 1.18.1`, `joblib 1.6.0`, `threadpoolctl 3.7.0`) for the AI evaluation (`py/ai_eval.py`); `py/requirements.txt` updated.
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

## B1 log (2026-10-18, board session 1, in progress)
- Programmed `build/inspect.bit` over JTAG (xsdb `program.tcl bit`). First attempt showed no LEDs after the HDMI cables were added later; re-programming fixed it (the design is lost if the board power is cycled).
- Result: LD0 and LD3 blink, LD1 and LD2 on (HDMI locked). Monitor (ViewSonic, not the TV) shows the laptop desktop through the board with the green window frame. No flicker seen by the user, colours correct. Photo: `data/photos/b1_passthrough_desktop_2026-10-18.jpg` (clock on screen 10:41).
- Not yet done: sw[0]/sw[1] check, phone camera on the screen, bolts on black mat, session start/end time (board hours used still to be written).

## B1 findings (2026-10-18)
- **Camera chain that works:** phone app **IP Webcam** (free, no watermark; DroidCam free versions are rejected: 640x480 in the classic client, moving watermark in the new one) -> Chrome page `http://192.168.1.23:8080/browserfs.html` (phone IP may change) -> **F11 full screen on the 1280x720 display** -> HDMI -> Zybo -> monitor. Laptop display is in **Extend** mode: DISPLAY1 = laptop panel 1920x1080, DISPLAY2 = the board's output 1280x720@60 at X=1920. `mss` monitor index 2 grabs exactly the picture the board receives -> use it for all captures (`data/raw/b1/hdmi_screen_*.png`).
- My own shell cannot reach the phone's TCP ports (ping works, Chrome works); not needed because we capture the screen.
- **Black mat + side lamp works**: mat gray mean about 16 (p99 36), bolt >100. Object is brighter than background -> polarity "object = gray > T" confirmed. A threshold anywhere 40..100 finds the bolt.
- **Size at 25 cm phone height:** bolt (about 10 mm) = 18 x 48 px (T=60, area 289 px) -> about 0.21 mm per pixel. Threshold 40 vs 100 changes the length by about 4 px (8 %) because the edges are soft -> the final accuracy needs more pixels: use the phone zoom (IP Webcam web page) or get closer; fix exposure/focus.
- A white object (stand/lamp arm) is in the top-right of the picture: keep it outside the inspection window.
- Old DroidCam clients are still installed (classic 6.5.3 and new 7.2.1); not used now.

- **Phone at about 17 cm (lowest the holder goes), frame `hdmi_screen_003_17cm.png`:** bolt about 60-70 px long (about 0.15 mm per px), sharp. Threshold 60+ is clean; threshold 40 gives about 30 mat-speckle blobs of 30-70 px (mat is fuzzy) -> use T >= 60 and/or the 3x3 filter later. At T >= 60 the bolt head separates from the shank as two blobs -> fine for moments/bbox (no connected components needed).
- Stand arm at the top right of the picture (x about 900-1050, y 0-400): inspection window must stay left of x = 880 or the arm must be turned away. Default window candidate: about 400 x 300 centred at (640, 360) -> x 440..839, y 210..509 (decide in M2).
- Board is NOT needed for frame capture (screen grab); capture sessions can continue without it. Board needed again for B2.

## M1 capture log
- 2026-10-18 session `s1` (`py/grab_hdmi.py`, data in `data/raw/s1/`, git-ignored): 147 frames: empty 3, bolt_good_01 27, _02 33, _03 27, _04 27, _05 30. 8 frames show the user's hand (listed in `data/raw/s1/hand_frames.txt`, exclude from accuracy sets, keep as a robustness test). Exposure was probably not locked (frame mean gray 21-37, higher with the hand). Still missing: more `empty` frames (only 3), bad/different parts, nuts (user has none), lamp-moved frames, parts table with ruler lengths (`data/parts.csv`).

- 2026-10-18 later: session `s1` now 285 frames: empty 21, bolt_good_01..05 (27/33/27/27/30), bad_a 30, bad_b 27, bad_c 30, bad_d 33 (other bolt/screw types, ruler lengths still to be measured). **Two brightness regimes in one session:** first 147 frames dark (mean gray about 20-37, mat p99 about 49), later 138 frames bright (mean about 52-64, mat p99 about 118, p99.9 about 141, parts up to 253). Fixed threshold 80 is clean on the dark set but marks about 65,000 mat pixels on the bright set; 150+ is needed there. -> strong evidence for exposure lock AND the Otsu auto-threshold (Standard tier, M6.3): record it in RESULTS. The bright set is a free "lighting change" test set. Cause of the change not yet confirmed by the user (lamp/room light/auto exposure).

- Parts table written: `data/parts.csv` (user ruler estimates 2026-10-18: good bolt about 10 mm, bad_a about 30, bad_b about 25, bad_c 15, bad_d 13 mm; uncertainty 1-3 mm). Picture of all types: `data/photos/part_types_s1.png`. NOTE: the good bolt (10 mm) and bad_d (13 mm) differ by only 3 mm: a good PASS/FAIL resolution test; a 10 mm bolt is the only long-run test of accuracy, so the 5-in-a-row ruler measurement is still wanted. Cause of the light change: not yet answered by the user.

## M2 results (2026-10-18)
- Spec decisions (data-based, see MEASUREMENT.md): default window x0=400 y0=240 W=480 H=360; polarity bit (bright object); **3x3 majority filter moved into the MVP** (from Standard) because the fuzzy mat gives specks; Otsu rejected (picks T=18..75 on dark frames); accumulator widths sized for the full frame (A 20 b, SX 30, SY 29, SXX 39, SYY 38, SXY 38 -> 40-bit regs); length = sqrt(12*l1+1) (exact for solid rectangles, self-test passes); new software status NOISY (box ratio > 1.5).
- Golden vs OpenCV: 285/285 frames agree in 5 settings (T120, T180, filter off, POL=0, full-frame window). Mutation test: 3 planted bugs each caught on 10/10 frames.
- Offline (T=120 dark / 180 bright): good bolts L_px median 71.0-73.6 (MAD 1.8-3.1); bad_d 84.3, bad_c 104.5, bad_b 149.3, bad_a 194.9 -> separable by length. 3-frame burst noise: median 1.33 px. Provisional k = 0.137 mm/px (from good = 10 mm).
- Problems found: (1) good parts only in dark frames, bad parts only in bright frames -> confounded, re-capture all parts in ONE locked lighting; (2) shiny cylinders: W_px measures the highlight stripe (about 10 px), not the real width; (3) fixed dust grains on the mat (679,218) and others -> clean the mat with tape before B2; (4) NVIDIA may send "limited range" RGB (16-235) over HDMI for 720p -> check/set "Full" range before B2, otherwise the board sees other gray values than the screen grab.

## Re-capture s2 (started 2026-10-18 about 12:50, paused by the user)
- Board output screen had vanished (board design lost, probably a power cycle): fixed by re-programming `build/inspect.bit` (xsdb `program.tcl bit`). **Rule: if Windows loses the 1280x720 second screen, re-program.**
- Camera state now: lamp lowered from full, picture mean gray about 35-38 (mat window p99.9 about 117, shiny parts about 250), steady over 5 s. IP Webcam exposure lock URL = `/settings/exposure_lock?set=on` (NO trailing dot; `?set=off` to unlock). Not yet confirmed locked.
- Ruler seen in the picture (red translucent 30 cm ruler at the bottom edge): numbers 0..10 cm at x = 578..1166 -> about 58.8 px per cm -> about 0.170 mm/px at the current phone height. The phone height was probably different in s1 (good bolt = 73 px equivalent length there), so **the ruler frame must be taken in the SAME setup as the part frames**. The mm tick lines were cut off by the picture edge: move the ruler up so its tick edge is fully visible.
- Plan for s2 (`py/grab_hdmi.py --session s2`): empty x5, ruler x2, bolt_good_01..05 x5 each, bad_a..d x5 each. Do not touch phone/stand/lamp during the session.

## M5 prep done offline while the user was away (2026-10-18)
- `docs/REGISTERS.md` (PROPOSED register map, to be confirmed/changed in M4) + `sw/common/insp_regs.h` (same map, safe `insp_read_result()` with frame-id check); `docs/PROTOCOL.md` (UART text protocol); `py/uart_log.py` (UART -> CSV logger, parser self-test passes).
- ARM maths in C: `sw/inspect/insp_math.[ch]` (pure C), PC test `sw/test/test_insp_math.c` + `scripts/test_arm_math.py`: **C = Python (measure.py) on all 285 frames** (centre, angle, L, W, box ratio, bbox, status, verdict; rel. error limit 1e-9); mutation (wrong window origin) detected on 244 frames. Compiler: MinGW gcc 10 inside Vivado (`C:\Xilinx5.1	ps\mingw.0.0\win64.o
tin\gcc.exe`), nothing installed.
- `sw/inspect/main.c` rewritten (result line per frame, text commands t p f o b w n k c s m z). **ARM app builds** (`vitis -s scripts/build_sw.py inspect`, -O2, M0 XSA): `build/sw/inspect.elf`, text 35,765 B. `build_sw.py` now adds `-lm` when an app includes math.h. Gotcha again: a leftover java/python process holding `~/fpga_ws` gives WinError 32 -> kill processes with 'fpga_ws' in the command line and rerun. The registers do not exist in hardware until M4, so it cannot do anything useful on the board yet.
- Old `edge_ai_regs.h` removed. Not tested on the board.

## 2026-10-19 update from the user
- **Board last day is 2026-10-21** (was 22 Oct). Updated job list (82 postings, `KCCI Jobs/kcci_jobs_detailed.md`): new postings are mostly PLC/maintenance/panel design; open to him and relevant: 63 Samjin E&I embedded/firmware, 57 DH Lighting embedded SW, 77 DH Lighting circuit design, 75/66 mechanical; FPGA/ISP (81 Pixelplus) and PCB (58) are Vietnam quota only. Machine vision stays only in #8, #4 (and #35/#19). The user doubts the project is too specific and has little excitement for it; discussion of continue/pivot pending his decision.

## M3+M4 hardware core (2026-10-19)
- New RTL: `insp_pkg.sv`, `meas_core.sv` (S0 threshold -> E event -> G event generator with pad column + flush row -> F1 2-row line buffer + 3x3 columns -> F2 majority -> A1-A3 DSP products + 39/38-bit accumulators + bbox), `insp_pipeline.sv` (result banks, video delay 4 + overlay = 6 clocks video latency), `insp_overlay.sv` (window frame coloured by verdict, bbox, centre cross, binary view), `axil_insp.sv` (register map = docs/REGISTERS.md), new `top.sv` (one 81-bit cdc_bus_sync for all settings). M0 `pixel_pipeline`/`roi_overlay` moved to `rtl/reuse/`, `axil_stub` deleted.
- Build (commit c45c811): **timing met, WNS +1.060 ns, WHS +0.033 ns**; 2,197 LUT (12.5 %), 2,655 FF, 0.5 BRAM, 3 DSP; no latches; only unused-port synth warnings.
- Tests: `scripts/sim_unit.py` tb_cdc + tb_axil_insp PASS (mutations: wrong bank start, old counted pointer -> both fail as expected). `scripts/sim_meas.py`: first run on the pre-review RTL: case default 285/285 result lines written, early frames bit-exact (run stopped after the review changed the RTL); **full run on the final RTL (commit c45c811): ALL 13 CASES BIT-EXACT** - default T=120 285/285 real frames, bright T=180 285/285, filter off 40, pol0 20, full frame 12, bottom-right corner 12, 1x1 / 3x2 / single-row windows, settings changed exactly at sof (10 frames), horizontal blanking of 1 clock (4), synthetic all-white (all accumulators at their maximum) / black / checkerboards / random with and without filter (5 + 5). Log `build/sim_meas_all.log` (about 40 min).
- RTL review (rtl-reviewer agent): 1 bug fixed (B1: AXI bank pointer could be one frame stale after a clk_acc reset -> pointer now = ~synchronized toggle, test added), risks fixed (R2 register init values, R3 flush cleared at sof), R1 handled in ARM (ignore 2 results after a window change), R4 (no set_max_delay on CDC data paths) documented in docs/CDC.md. Byte-strobe test made able to fail.
- `py/still_test.py`: board-side bit-exact test with recorded frames shown as still images (also detects limited-range RGB). B2 checklist written.

## B2 log (2026-10-20, board session 2, in progress)
- Board serial port is **COM11** (not COM16/17 this time). Program: `xsdb scripts/program.tcl all inspect` -> ID 0x1A570001, results every frame, skipped=0, video locked (first 739 frames).
- **Still test on the real board: 20/20 frames bit-exact vs golden** (`py/still_test.py COM11 --n 20`, frames from s1 shown full screen on the board's 1280x720 screen, 5 consecutive results each, A exact, cx/cy/L/W within rounding). Proves: full-range RGB reaches the FPGA (no limited-range problem), filter + sums + banks + AXI read are correct on hardware.
- **New phone** (IP Webcam at 192.168.1.38:8080, same app/steps; exposure lock via `/settings/exposure_lock?set=on`, unlock `set=off`; lamp dimmed to get mat mean gray about 32): s2 captured in `data/raw/s2` (168 frames: ruler 6, nothing 15, good bolts 81, bad_a..d 15 each), brightness steady 31.8-34.5 over the whole session. Empty-window worst A at T=120 with filter: 4 px.
- **Calibration (ruler in picture, same setup):** digits 2..9 cm span about 412 px -> 58.9 px/cm -> 0.1698 mm/px on the ruler plane; x1.018 for the ruler thickness (about 3.5 mm above the mat at about 20 cm) -> **0.1728 mm/px** (uncertainty about 2 %; the mm tick lines were not usable, mat texture shows through the translucent ruler).
- **Offline measurement s2 (T=120, filter on, median over frames):** good bolt L 67.7 px = **11.7 mm** (MAD 2.3 px; user's rough guess was 10 mm), W 9.2 px; bad_a 192.5 px = 33.3 mm; bad_b 141.5 = 24.5 mm; bad_c 95.5 = 16.5 mm; bad_d 78.1 px = 13.5 mm (W 17 px, much wider than the good bolt's 9). User ruler estimates: a ~30+, b ~25, c ~15, d ~13 -> agreement within 1.5 mm. 14 of 81 good-bolt frames and a few bad ones come out NOISY (far specks, box ratio > 1.5): to be checked live with different T.
- ARM configured for the live test: `t 120`, `c 0.1728`, `n 11.7 1.2` (nominal 11.7 mm, tolerance 1.2 mm).
- **First live evidence run** (`data/runs/20261020_evidence.csv`, 8,887 lines, firmware v1: no smoothing, length tol only): repeatability of a truly still bolt **std 0.13 mm (0.77 px)**, 661/661 valid; but placement-to-placement spread of a good bolt 10.1-12.7 mm (angle / glare), good bolts PASS only 63 % of frames with L 11.6 +- 1.0 mm; bad_d wrongly passed. Offline tuning on the logged lines: width check + median of 9 -> good PASS 87 % / wrongly FAIL 2 %, bad FAIL 83 % / wrongly PASS 2 % (tuned on the same data).
- **Firmware v2** (median of last 9 frames, `v` width check, `g` command) FIRST VERSION HAD A DESIGN BUG: every NOISY (speck) frame reset the history, so 75 % of the time the board was in warm-up (undecided): found by comparing live `g 0` vs `g 1` with the same bolt (28 % raw NOISY frames from a flickering speck in the live camera picture; offline stills of the same setup: 0 % NOISY). The bad recording is kept as `data/runs/20261020_v2_smoothing_reset_bug.csv`. **v3 fix**: NOISY frames are skipped and the last median is held (max 12 in a row); NOPART/EDGE clear the history. Live check with a good bolt: 425/425 PASS, L 11.60 mm (11.39..11.74).
- **Run with firmware v3** (`data/runs/20261020_v3_mouse_pointer_in_picture.csv`, 8,912 lines): bolts 01+02 PASS in all 6 placements, bad parts FAIL 11 of 12 placements (0 % of bad frames passed), but bolts 03-05 often undecided/odd (L 16-22 mm, W 5.9 mm, same centroid near (690, 400) in many placements = a second bright object). Cause found by live test: the **mouse pointer** was resting on the board's screen (Windows sends it in the HDMI video, the hardware counts it as an object). With the pointer parked on the laptop screen: 361/361 PASS live. Rule: keep the mouse off the board screen (DISPLAY2) during any recording. Repeat run follows.
- **FINAL EVIDENCE (firmware v3, pointer parked, `data/runs/20261020_final.csv`, 8,942 lines; analysis `py/analyze_evidence.py`):**
  - **Repeatability** (bolt_good_01 not touched, 3 positions, ~530 lines each after dropping the first 20 %): length std **0.065 / 0.056 / 0.073 mm** (0.37 / 0.33 / 0.42 px), range 11.25-11.60 / 11.50-11.82 / 10.93-11.36 mm, centre std < 0.4 px, 530/530, 529/529, 532/532 valid and PASS.
  - **PASS/FAIL**: placement level (majority verdict, 3 placements per part): **good 15/15 PASS; bad 11/12 FAIL, 1 undecided, 0 wrongly passed.** Frame level (first quarter of each 3 s recording dropped): good PASS 99.6 %, FAIL 0.0 %, undecided 0.4 % (n = 2,749); bad FAIL 92.5 %, wrongly PASS 0.7 %, undecided 6.8 % (n = 2,207).
  - Per-part length (median over placements, mm; ruler estimates in brackets): good bolts 11.06-11.47 (about 10-12); bad_d 13.22 (13), bad_c 16.27 (15), bad_b 20.87 (25), bad_a 27.34 (30+). Spread of the same part over placements: good 0.3-2.2 mm, bad_a 5.3 mm, bad_b 7.0 mm: shiny parts change length with angle/glare, so absolute accuracy of the long shiny parts is poor; the ruler reference itself is only +-1 mm and the calibration +-2 %.
  - **Caveat (in-sample)**: the rule (T=130, length 11.3 +- 1.6, width 1.3 +- 0.7, median of 9) was tuned on the earlier recording of the SAME parts, then tested again on a new recording with new placements. Not a blind test.
  - **Frame rate**: 58,605 video frames seen, 58,604 results, **skipped = 0** (ARM counter since program start, about 16 min at 60 fps); a dedicated 60 s test was not possible because evidence.py held the serial port. Video latency by design: 6 pixel clocks = 81 ns (pipeline depth, not measured).
  - Empty mat: 301 of 363 lines NOPART; the rest are the first lines after pressing Enter (see check).
- Rule now on the board: T=130, k=0.1728 mm/px, length 11.3 +- 1.6 mm, width 1.3 +- 0.7 mm.
- **60 s frame-rate test (board, results line off):** 3,602 video frames and 3,602 results in 60.03 s = **60.003 fps, 0 skipped.** Hardware vs golden: 20/20 still frames bit-exact on the board.
- **CORRECTION (2026-10-20 night, found while building the viewer):** each evidence recording began with about 62 stale lines (old output held by the USB-serial chip, visible as a frame-number jump of about 1,000 after line 62). `strip_stale_prefix()` in `py/uart_log.py` removes them exactly; `py/analyze_evidence.py` and `py/viewer.py` use it. Corrected final numbers (RESULTS.md and README updated): repeatability std 0.064 / 0.057 / 0.073 mm; placement level unchanged (good 15/15 PASS, bad 11/12 FAIL, none wrongly passed); frame level good PASS 97.4 % / wrongly FAIL 0.7 % / undecided 1.9 %, bad FAIL 92.8 % / wrongly PASS 0.7 % / undecided 6.5 %; empty mat 301/301 NOPART. The ARM never stalled (0 skipped); the still test could only have shown false failures from stale lines, not false passes.
- **Python viewer** `py/viewer.py` (tkinter, no extra install): live from the serial port or replay of a CSV (`--replay ... --speed 30`), PASS/FAIL tile, numbers, yield, trend chart with tolerance band, `--log` CSV in live mode, `--selftest` without a window. Replay of the final evidence: 22 parts counted (PASS 14, FAIL 8). The window starts without errors (8 s run).
- **AI layer evaluated offline** (`py/ai_eval.py`, `docs/AI.md`): type recognition tree 86.2 % frames / 25 of 30 recordings (kNN 83.7 %); unseen-defect rejection (train on good only): one-class model 98.7 % good accepted / 100 % bad rejected vs tolerance rule 99.5 % / 99.0 % -> AI not better than the rule; not run on the board, tree not exported to C.
- **Demo material (`data/photos/b2/`):** 3 photos + 4 video stills (green PASS, red FAIL long/short part, empty white frame, in git) + 87 MB demo video `b2_demo_pass_fail.mp4` (portrait 1080x1920, 40.6 s, green/red/cyan box visible; NOT in git, back it up outside the repo, upload to YouTube later).
- **Saved for the release without the board:** `artifacts/` (git-ignored): inspect.bit, inspect.xsa, inspect.elf, ps7_init.tcl, **BOOT.bin built (2.2 MB; NOT tested: no SD card was available)**. Reports (timing, utilization, power, CDC, DRC) in `docs/reports/`.
- Not measured / limits to state in RESULTS: no SD-card boot test; latency only by design (6 clocks = 81 ns); accuracy limited by ruler +-1 mm and calibration +-2 %; rule tuned on the same parts (in-sample); one camera/lamp setup; no multi-part test.
- Done in B2 (was: still to do): s2 capture, ruler calibration, live PASS/FAIL, evidence logs, photos/video, frame-rate test.

## Open problems
- Accuracy reference: a 1 mm ruler is coarse. Plan: measure 10 identical parts in a row and divide by 10; put the ruler in the camera view for calibration. A cheap digital caliper would make the accuracy result stronger (user to decide).
- Warm lamp + shiny metal parts may give reflections; test in M1 before choosing parts.

## Next step
M1 (Sonnet / medium). Before it: user installs DroidCam on the phone, finds stand, bolt length in mm, black paper/cloth, old SD card. Then the assistant writes `py/capture_frames.py` and a B1 checklist (program pass-through over JTAG: `xsdb scripts/program.tcl bit`).
