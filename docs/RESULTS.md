# RESULTS — every number, with the method

All numbers were measured by the scripts named next to them, on 2026-10-18 to 2026-10-20. Nothing here is estimated unless it says
"by design". Raw data: `data/runs/20261020_final.csv` (board evidence), `data/raw/s1` and `data/raw/s2` (recorded frames, kept outside git).
Setup: Zybo Z7-10, phone camera (IP Webcam) 17-25 cm above a black mat, shiny metal bolts about 10-12 mm long, one lamp, exposure locked.

## 1. Correctness

| What | Result | Method |
|---|---|---|
| Golden model vs OpenCV | 285 / 285 frames agree, 5 settings (T 120, T 180, filter off, polarity 0, full-frame window) | `py/check_opencv.py`: threshold mask, 3x3 filter, raw moments m00..m11, bounding box, histogram. 3 deliberately planted bugs were each caught on 10 / 10 frames |
| RTL vs golden model (simulation) | **13 / 13 cases bit-exact**: 285 + 285 real frames (T 120 and T 180), filter off (40), polarity 0 (20), full frame (12), bottom-right corner (12), 1x1 / 3x2 / single-row windows, settings changed exactly at frame start (10), horizontal blanking of 1 clock (4), synthetic all-white frames that reach the maximum values of all accumulators, black, checkerboards, random (5 + 5) | `scripts/sim_meas.py` in Vivado xsim, all ten values (A, SX, SY, SXX, SYY, SXY, UMIN, UMAX, VMIN, VMAX) compared per frame |
| Register block | pass; planted bank-pointer bug and the first (counted) pointer design both make it fail | `tb/tb_axil_insp.sv`: two clocks, reset during traffic |
| ARM maths in C vs Python | 285 / 285 frames equal (relative error < 1e-9); a wrong window origin is detected on 244 frames | `scripts/test_arm_math.py` (MinGW gcc 10 from Vivado) |
| **Real hardware vs golden model** | **20 / 20 frames bit-exact on the board**: each recorded frame shown full screen on the board's HDMI input, 5 consecutive result lines, A exact, centre / length / width within printing rounding | `py/still_test.py` on COM11 |

## 2. Speed and delay

| What | Result | Method |
|---|---|---|
| Video | 1280x720 at 60 Hz, pixel clock 74.25 MHz | EDID with only 720p (`scripts/make_edid.py`) |
| Frame rate | **3,602 video frames and 3,602 results in 60.03 s = 60.003 fps, 0 skipped** | ARM counters `PIX_FRAMES`, `results`, `skipped` before and after 60 s (result lines off) |
| Longer run | 58,605 frames, 58,604 results, 0 skipped (about 16 min) | same counters since program start |
| Video delay | 6 pixel clocks = 81 ns **by design** (position 1, delay 4, overlay 1) | pipeline depth in `rtl/insp_pipeline.sv`; not measured on a scope |
| Result age | results of frame N are used and drawn from frame N+1 | design (no frame buffer) |
| UART load | about 70 bytes x 60 lines/s = 4.2 kB/s of 11.5 kB/s | `docs/PROTOCOL.md` |

## 3. Size, timing, power (Vivado 2025.1, XC7Z010-1, `docs/reports/`)

| What | Result |
|---|---|
| Slice LUTs | 2,197 of 17,600 (12.5 %) |
| Slice registers | 2,655 of 35,200 (7.5 %) |
| Block RAM | 0.5 of 60 tiles (the 2-row filter line buffer) |
| DSP48 | 3 of 80 (u*u, v*v, u*v) |
| Timing | met: **WNS +1.060 ns, WHS +0.033 ns**, 0 failing endpoints (5,649) |
| Power (Vivado estimate, not measured) | 2.017 W total, 1.887 W dynamic, mostly ARM and DDR |
| CDC report | 5 critical findings (CDC-7 x3, CDC-11 x2), **all inside Digilent's `dvi2rgb` IP**, none in own logic; 113 warnings of type CDC-15 (clock-enable controlled structures, the intended request/acknowledge crossing). Details: `docs/CDC.md` |

## 4. Measurement quality (board, firmware v3)

Rule on the board: threshold T = 130, calibration 0.1728 mm per pixel, length 11.3 +- 1.6 mm, width 1.3 +- 0.7 mm, median of the last 9 valid frames.

| What | Result | Method |
|---|---|---|
| **Repeatability** (bolt not touched, 3 positions, about 530 results each) | length std **0.064 / 0.057 / 0.073 mm** (0.37 / 0.33 / 0.42 px), range 11.25-11.60 / 11.50-11.82 / 10.93-11.36 mm; centre std < 0.42 px; all results valid | `py/evidence.py` + `py/analyze_evidence.py`; 540 / 540 / 599 lines after removing the stale prefix and the first 10 % |
| **PASS/FAIL per placement** | good bolts **15 / 15 PASS**; bad parts **11 / 12 FAIL, 1 undecided, 0 wrongly passed** | majority verdict of 3 placements x 3 s per part (5 good bolts, 4 other part types) |
| PASS/FAIL per frame | good: PASS 97.4 %, wrongly FAIL 0.7 %, undecided 1.9 % (n = 2,722); bad: FAIL 92.8 %, wrongly PASS 0.7 %, undecided 6.5 % (n = 2,237) | same data; stale prefix of each recording removed exactly, then the first 20 lines (0.33 s: hand leaving, 5-frame warm-up of the median) |
| Length of the same part in different placements | good bolts 0.3-2.2 mm spread; bad_a 5.2 mm, bad_b 7.0 mm | per-part median of placements |
| Empty mat | **301 / 301 lines NOPART** (no false detection) | `py/evidence.py` empty-mat step, stale prefix removed |

Calibration: ruler in the picture, same setup. Numbers 2 to 9 cm span 412 px = 58.9 px/cm = 0.1698 mm/px on the ruler plane, x 1.018 for the ruler thickness above the mat = 0.1728 mm/px, uncertainty about 2 %. The mm tick lines of the see-through ruler were not usable.

Typical measured lengths (equivalent length, mm; ruler estimate in brackets): good bolts 11.06-11.49 (10-12), bad_d 13.22 (13), bad_c 16.24 (15), bad_b 20.84 (25), bad_a 27.39 (30+).

**Correction found while checking (2026-10-20 night):** each evidence recording began with about 62 *stale* result lines: the USB-serial chip still held about 1 s of old output that the PC-side buffer flush cannot clear (visible as a jump of about 1,000 in the frame number after line 62). The first version of the analysis only dropped the first quarter of each recording, so some lines of the previous part leaked into the next recording and the frame-level rates looked better than they are (good PASS 99.6 % instead of 97.4 %). The analysis now removes the stale prefix exactly (`strip_stale_prefix` in `py/uart_log.py`). The ARM never stalled: 0 skipped results.

## 5. What the evidence runs taught us (all documented in `notes/PROGRESS.md`)
- A fixed threshold fails when the camera brightness changes (mat gray 18 vs 50 in one session): exposure lock was needed.
- The mouse pointer on the board's screen was counted as a part: keep it off the video.
- A USB-serial chip keeps about 1 s of old data that a buffer flush does not clear: a logger must detect the frame-number jump and drop that prefix (found when the viewer counted twice as many parts as there were recordings).
- Specks of mat fluff flicker in the live camera picture (28 % of raw frames at T 130): the 3x3 filter and a median over the last frames are needed; a first smoothing version that reset on every noisy frame left the board undecided 75 % of the time (found by live comparison, fixed).
- The measured length depends on T (11.98 mm at T 120, 10.27 mm at T 160 for the same bolt): always calibrate at the T that is used.

## 6. Limits (honest list)
- The rule was tuned on an earlier recording of the **same parts**, then tested on a new recording with new placements: not a blind test.
- Accuracy is limited by the ruler (+-1 mm) and the calibration (+-2 %); no caliper was available. "Accuracy vs caliper on 10 parts" from the plan was **not** done.
- Shiny parts change their measured length with their angle (glare): long parts vary by 5-7 mm.
- One camera, one lamp, one background; one part at a time; no multi-part counting.
- SD-card boot was not tested (no SD card); `artifacts/BOOT.bin` was built but never run.
- Latency is by design, power is Vivado's estimate.
