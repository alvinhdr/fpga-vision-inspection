# PLAN — Real-Time FPGA Vision Inspection Station

Written 2026-10-12, before the project started. The plan is **progressive, not day-by-day**: do the milestones in order, as fast as the user's free time allows. Milestones marked **[BOARD]** need the Zybo; everything else does not. Read `the project instructions` first: its rules always win over this file.

---

## 1. The idea in one paragraph

A phone camera looks down at a small part (coin, washer, nut) on white paper. The phone is used as a webcam by the laptop; the laptop shows the camera full screen at 1280×720 and sends it over HDMI into the Zybo Z7-10. Hand-written SystemVerilog measures the part **while the pixels stream past** (no frame buffer): it thresholds the picture inside an inspection window and sums, per frame, the pixel count, Σx, Σy, Σx², Σy², Σxy, the bounding box and a gray-level histogram. The ARM turns those sums into centre, angle and size in millimetres and decides PASS/FAIL against a tolerance. The result is drawn on the live video (box, cross, size, big PASS/FAIL) and sent over UART to a PC operator app (Python first, then C# WPF) with yield, trend chart and CSV log.

**Interview pitch:** "The FPGA does every per-pixel operation at 55 million pixels per second with a few clocks of delay; the ARM only does about twenty operations per frame. I verified the hardware bit-exactly against a Python model on real camera frames and checked that model against OpenCV, then measured repeatability and accuracy against a caliper."

---

## 2. Scope tiers (protect the minimum first)

| Tier | Contents | Must be done before the board is returned? |
|---|---|---|
| **MVP** | Window + fixed threshold + streaming moments + bounding box; ARM computes size in mm and PASS/FAIL; overlay box/cross + PASS/FAIL colour; UART result lines; SD-card demo; recorded logs and video | **YES** |
| **Standard** | Text overlay (size in mm, "PASS"/"FAIL" letters); 256-bin histogram + Otsu auto-threshold (lighting changes); 3×3 binary majority (noise) filter with line buffers; binary "what the FPGA sees" view; Python live viewer; C# WPF operator app with replay | FPGA parts yes; PC apps can be done after |
| **Stretch** | Several parts at once (streaming connected-component labelling); sub-pixel edge measurement along a scan line; hole/defect check; orientation check; PC OpenCV speed comparison | only if time is left |

If board time gets short: finish MVP on the board, record all data, and do the rest offline.

---

## 3. Board-time budget (~10 hours over ~5 days)

| Session | When | Length | Purpose | Must be ready before |
|---|---|---|---|---|
| **B1** | as early as possible | 0.5–1 h | Check camera → laptop → HDMI → board → TV with the **old project's SD card** (pass-through works there); set camera height, lighting, laptop 1280×720; confirm which phone-webcam app works full screen | nothing new (old SD card + M1 setup) |
| **B2** | after M5 | 2 h | First live measurement (MVP): UART results, overlay, calibration, quick repeatability; write a fix list | M4 + M5 built, simulated, timing met |
| **B3** | after M6 (or right after B2 fixes if short on time) | 2 h | Record the **evidence**: repeatability log, accuracy set vs caliper, labelled good/bad set, photos | M6 (or MVP fixes) built and simulated |
| **B4** | before returning the board | 2 h | Final: SD card BOOT.bin, frame-rate + latency counters, **demo video**, Python/C# app live test | final build; demo script written |
| **B5** | spare | 1–2 h | Retakes, anything that failed | — |

Rules: never debug from zero on the board; simulate first. Every session starts from a checklist (section 7) and ends with notes in `notes/PROGRESS.md` (what was measured, files saved, hours used).

---

## 4. What to reuse from the previous project

Source: `<projects>\FPGA Edge AI Video` (same author, MIT). **Copy** files (do not link), keep the comment headers, update the project name, and note "adapted from fpga-edge-ai-video" in each header.

| Previous file | Use here |
|---|---|
| `third_party/vivado-library` (submodule, commit `f4613ff`) | add the same submodule |
| `constraints/zybo_z7_10.xdc`, `zybo_z7_10_impl.xdc` | as is (pins, clocks, async clock groups) |
| `rtl/edid_720p_only.data`, `scripts/make_edid.py` | as is (laptop can only send 720p) |
| `rtl/video_pkg.sv` (R-B-G order), `pix_pos_counter.sv`, `rgb2gray.sv`, `ram_tdp.sv` | as is |
| `rtl/cdc_sync_2ff.sv`, `cdc_pulse_sync.sv`, `cdc_bus_sync.sv` + `tb/tb_cdc.sv` | as is |
| `rtl/axil_regs.sv` + `tb/tb_axil_regs.sv` | starting point for the new register map |
| `rtl/roi_overlay.sv`, `digit_overlay.sv`, `font_rom.sv`, `font_digits_8x8.mem`, `conf_bar_overlay.sv`, `ai_view_overlay.sv` | starting points for window frame, text, bar and binary view overlays |
| `rtl/roi_capture.sv` | pattern for window handling, settings latched at frame start, frame-done toggle, bank flip |
| `rtl/top.sv`, `pixel_pipeline.sv` | starting point for the new top level (remove the CNN, keep HDMI, clocks, PS, CDC wiring) |
| `scripts/build_hw.tcl`, `build_sw.py` (has the Vitis fixes and `-O2`), `program.tcl`, `make_boot.py` | as is, rename project |
| `scripts/video_stream.py`, `sim_pixel_pipeline.py`, `sim_unit.py` | PNG → simulated 720p stream → RTL → compare; adapt to the new checks |
| `scripts/capture_roi.py`, `bench_mnist.py` | patterns for UART tools |
| `sw/edge_ai_demo/main.c`, `sw/common/edge_ai_regs.h` | patterns for UART commands, `f` frame-rate test, timer use (`usleep` first!) |
| `scripts/make_diagram.py` | black-and-white diagrams.net-style block diagram (.drawio + PNG) |
| `.gitignore`, `LICENSE` (MIT) | copy |

Do **not** copy: CNN RTL, ML folders, MNIST files, results/notes of the old project.

---

## 5. Milestones (in order)

Each milestone lists: goal · tasks · done when (evidence) · model/effort · what to teach. At the end of each: update `notes/PROGRESS.md` and `docs/LEARNING.md`, commit, push, tag `m<N>-done`, short plain-English summary to the user.

### M0 — Project setup (no board)
- Confirm with the user: repo name, GitHub repo (private), which parts and which measuring tool (ruler/caliper) they have, which phone.
- `git init`, submodule, folder structure (section 6 of the project instructions), copy the reuse files (section 4), `.gitignore`, `notes/PROGRESS.md`, `docs/LEARNING.md`.
- Check tools still work: Vivado/Vitis 2025.1, Python venv (`numpy`, `opencv-python`, `pillow`, `pyserial`, `mss` for screen capture), git, gh.
- **Done when:** repo pushed; a first `build_hw.tcl all` of the reused pass-through top runs and meets timing (no CNN), so the build flow is proven before any new RTL.
- **Model:** first message `opus`/`high` (read the plan, ask questions, confirm scope); then `sonnet`/`medium` for the setup work.
- **Teach:** what each reused file does (short), why reuse is normal in industry.

### M1 — Camera setup and data capture (no board; phone + laptop)
- Choose the phone-webcam app (Windows Phone Link camera, DroidCam, Iriun… test which gives a clean full-screen 1280×720 picture). Build a stand (books/box) so the phone looks straight down from 20–30 cm. White paper, desk lamp from the side, no shadows, lock exposure/focus if the app allows.
- Parts: at least 10 identical "good" parts + several "bad" ones (different size, broken, wrong type). User measures each with ruler/caliper → `data/parts.csv` (id, type, measured size in mm, good/bad).
- `py/capture_frames.py`: capture what the **HDMI output will contain** — the laptop screen (1280×720, camera app full screen) with `mss`, or the camera stream with OpenCV if the app has no clean full screen. Save PNG frames: each part, several positions and angles, plus empty-window frames, plus a few lighting changes. Keep big sets outside git; commit a small sample (≤ 20 frames).
- Decide the default inspection window (for example 640×480 in the centre: x 320–959, y 120–599) from the real pictures.
- **Done when:** ≥ 200 frames saved and labelled; parts table filled; window size chosen.
- **Model:** `sonnet`/`medium`.
- **Teach:** lighting and contrast in machine vision (why white background + side light), perspective (camera must be square to the table), why we record data before touching the hardware.

### M2 — Measurement spec, golden model, OpenCV cross-check (no board)
- Write `docs/MEASUREMENT.md` **before any RTL**: exact integer math for gray conversion (same as `rgb2gray.sv`), threshold (dark part on light paper: pixel is "object" if gray < T), window coordinates (relative to window origin), accumulators and their **bit widths** (window 640×480: area ≤ 307,200 → 19 bits; Σx ≤ 1.97·10⁸ → 28 bits; Σx², Σxy ≤ 1.26·10¹¹ → 37 bits; use 40-bit registers, read as two 32-bit AXI words), bounding box, histogram (256 bins × 19 bits), the 3×3 majority filter (Standard tier), what happens on an empty window.
- Per-frame math done by the ARM (float is fine on the A9): centre `cx = Σx/A`; central moments `μ20 = Σx²/A − cx²` (same for μ02, μ11); angle `θ = ½·atan2(2μ11, μ20 − μ02)`; equivalent diameter `d = 2·√(A/π)`; ellipse axes from the eigenvalues of the 2×2 covariance; mm = px × calibration; PASS if |value − nominal| ≤ tolerance and A > minimum area.
- `py/golden.py` (NumPy, integers only) computes all accumulators for a frame. `py/check_opencv.py` compares with OpenCV (`cv2.threshold`, `cv2.moments` raw moments m00/m10/m01/m20/m02/m11, `cv2.boundingRect`) on all captured frames — they must agree exactly (if a convention differs, document it).
- `py/measure.py`: the ARM's per-frame math in Python, to predict mm/PASS/FAIL offline on the captured frames (first accuracy estimate before the board!).
- **Done when:** golden = OpenCV on all captured frames; offline size estimates vs `parts.csv` look sensible; MEASUREMENT.md reviewed with the user.
- **Model:** `opus`/`high` for the spec and widths; `sonnet`/`medium` for the Python code.
- **Teach:** image moments in plain words (area = how many pixels, centre = average position, second moments = how spread out/turned), why sums are perfect for streaming hardware, why the ARM does the divisions.

### M3 — New top level with pass-through + inspection window overlay (no board)
- From the reused files: top level with HDMI in/out, PS block, AXI-Lite, clocks, EDID; remove the CNN. Add the inspection window frame overlay with an AXI-adjustable window position/size.
- Testbench via `video_stream.py` (PNG → 720p stream → RTL → PNG → compare with Python reference) using **real captured frames**.
- **Done when:** sims pass bit-exact; full build meets timing; BOOT.bin can be made.
- **Model:** `opus`/`medium` (RTL), `sonnet`/`medium` (scripts).
- **Teach:** what changed vs the old top, how video timing (DE, blanking) works again.

### B1 — **[BOARD]** First board session (can happen any time after M1, even before M3)
- Use the **old project's SD card** (it passes video through) or the M3 build if ready. Checklist: laptop 1280×720 (EDID), camera app full screen, window position matches the parts, lighting OK on the TV, board LEDs (LD2 = HDMI locked).
- If M3 is built: program over JTAG (`program.tcl all <app>`), check the window overlay.
- **Done when:** user confirms the camera picture appears on the TV through the board; photos taken; setup notes (camera height, lamp position, app settings) written so the setup can be rebuilt the same way later.

### M4 — RTL measurement core (no board)
- `rtl/threshold_window.sv`: gray → threshold (register value) → object bit, only inside the window.
- `rtl/moments_acc.sv`: streaming accumulators (area, Σx, Σy, Σx², Σy², Σxy) — multiply-adds map to DSP48; pipeline them so 74.25 MHz has margin.
- `rtl/bbox_track.sv`: min/max x and y of object pixels.
- `rtl/result_bank.sv`: at the end of the window, copy all accumulators into one of **two banks**; a frame counter + ready-bank bit tell the ARM which bank is complete (same idea as the old two-bank ROI buffer). Design the crossing to the 100 MHz AXI side carefully (`opus`/`high` first): either AXI reads the stable bank through a synchronized bank bit, or the whole result set crosses with a req/ack handshake. Document in `docs/CDC.md`.
- `rtl/axil_regs.sv`: new register map (ID, CTRL, THRESH, WINDOW pos/size, FRAME_CNT, READY_BANK, results lo/hi words, BBOX, later HIST/OTSU, TEXT RAM). Write the map in `sw/common/insp_regs.h` too.
- Overlays (MVP): bounding box rectangle and centre cross from the **previous** frame's results (computed in hardware from the bank: centre needs a division → either draw only the bbox + its middle in hardware, or let the ARM write cx/cy into an overlay register — recommended: ARM writes them).
- Testbenches: unit tbs for each module; system tb streams ≥ 100 **real captured frames** and compares every accumulator with `py/golden.py` (bit-exact); a mutation test (break one thing on purpose, the tb must fail).
- **Done when:** all sims pass; `rtl-reviewer` agent run and real findings fixed; full build meets timing; resources noted.
- **Model:** `opus`/`high` for the CDC/banking design; `opus`/`medium` for RTL + tbs; `opus`/`xhigh` if a mismatch is not fixed in 2 tries.
- **Teach:** streaming vs frame buffer; DSP48 multiply-accumulate; why two banks; how the tb proves bit-exactness; the read-modify-write hazard idea (needed later for the histogram).

### M5 — ARM application (no board)
- `sw/inspect/main.c`: wait for a new ready bank (frame counter), read results, compute centre/angle/size/mm, PASS/FAIL, write overlay registers (cx, cy, PASS/FAIL colour), print one result line per frame.
- **UART protocol** (machine-readable, documented in `docs/PROTOCOL.md`), e.g. `R,<frame>,<area_px>,<cx>,<cy>,<w_px>,<h_px>,<angle_deg>,<diam_mm>,<PASS|FAIL|NOPART>`; ~70 bytes × 60 fps ≈ 4.2 kB/s, fits 115200 baud (11.5 kB/s). Commands from the PC: set threshold, window, nominal size and tolerance, calibrate with a reference part of known size (`k <mm>`), status, frame-rate test (`f`, reuse the old one), single-shot mode.
- Calibration stored in RAM (and printed so the PC can save it).
- `py/uart_log.py`: save every line to a CSV with a timestamp (this is the raw evidence for RESULTS).
- **Done when:** app builds with `-O2`; a "fake results" unit test on the PC (feed recorded golden accumulators into the same C math compiled for the PC, or into `py/measure.py`) gives the same mm/PASS values.
- **Model:** `sonnet`/`medium`.
- **Teach:** why the ARM does the floating-point math, how calibration works, what a protocol needs (start marker, fields, checks).

### B2 — **[BOARD]** First live measurement
Checklist (section 7). Calibrate with one reference part; place each good part a few times; check PASS/FAIL; log 1–2 minutes of UART data; take photos; note problems. **Done when:** live PASS/FAIL works on the TV and in the log for good and bad parts.

### M6 — Standard features (no board, then B3)
Do in this order, stop when time runs out:
1. **Text overlay**: extend the 8×8 font (digits, `. m P A S F I L N O R T`), a small character RAM written by the ARM (e.g. "24.13 mm", "PASS"), drawn scaled ×4; big green/red frame around the window.
2. **Binary view** switch: show the thresholded pixels inside the window ("what the FPGA sees").
3. **Histogram (256 bins, two banks in BRAM)** + **Otsu threshold** computed by the ARM and written back for the next frame → robust to lighting changes. Handle the read-modify-write hazard when two neighbour pixels hit the same bin (pipeline forwarding) — a strong interview topic. Test with frames at different brightness.
4. **3×3 binary majority filter** with two line buffers (removes single noisy pixels); golden model updated first, bit-exact again.
- **Done when:** each feature is simulated bit-exact (golden updated) and built with timing met.
- **Model:** `opus`/`medium` (RTL); `sonnet`/`medium` (C, Python).

### B3 — **[BOARD]** Record the evidence (most important session)
Using the latest working build, record (all saved by `py/uart_log.py` into `data/runs/<date>_<name>.csv`, plus photos):
1. **Repeatability:** one part, not moving, ≥ 600 frames (10 s) → std. dev. of size in px and mm. Repeat for 3 positions in the window.
2. **Accuracy:** each of the ≥ 10 measured parts, 60 frames each → mean size vs caliper → error per part, mean and max error.
3. **PASS/FAIL correctness:** a labelled sequence of good and bad parts (≥ 20 placements) → confusion table.
4. **Lighting test** (if Otsu is done): lamp on/off or moved, fixed threshold vs Otsu → PASS/FAIL stability.
5. Frame-rate test `f` (frames vs results in 60 s, 0 skipped expected) and the latency counters.
6. Photos of the TV for README.

### M7 — Final build and demo (then B4) — **[BOARD] for B4**
- Freeze the feature set. Final build (timing met), BOOT.bin, `make_boot.py --copy-to <SD drive>` (check the drive letter, only BOOT.bin is replaced).
- Write the **demo video script** (30–60 s, landscape, steady): board + cables (3 s) → empty window shows nothing → good part: PASS + size → bad part: FAIL → move/rotate part (angle and box follow) → lamp change (Otsu keeps working) → PC app window with yield and trend.
- B4: boot from SD, final `f` test, record the demo video (and a silent trimmed copy for YouTube), test the Python viewer live; C# app live if ready (else replay mode is enough).
- **Then return the board.** Note in PROGRESS.md the date it was returned.
- **Model:** `sonnet`/`medium`.

### M8 — PC operator apps (no board needed: replay recorded logs)
- **M8a Python live viewer** (fast, user knows Python): `py/viewer.py` — serial or replay-from-CSV, live numbers, PASS/FAIL, yield, trend plot. `sonnet`/`medium`.
- **M8b C# WPF operator app** (user has never used C#; teach from zero, small steps):
  1. Install .NET SDK (LTS) and Visual Studio 2022 Community (or VS Code + C# Dev Kit) — ask the user first.
  2. Console app: read a recorded CSV, parse lines into a `Measurement` class, print stats (teaches types, classes, LINQ).
  3. WPF window: big PASS/FAIL tile, last size, yield %, count; MVVM with CommunityToolkit.Mvvm (teaches data binding).
  4. Trend chart (a free chart library such as ScottPlot) of size with tolerance lines.
  5. Serial port (System.IO.Ports) **and** replay mode from CSV at real speed (works without the board).
  6. Settings panel that sends commands (threshold, tolerance, calibration) — testable only with the board, so build the command layer with a fake serial port for tests.
  7. CSV export, simple log of FAIL events.
  - `opus`/`medium` for the app architecture (step 3 design), `sonnet`/`medium` for the rest.
- **Done when:** app runs the recorded B3 logs in replay mode; screenshots for README.
- **Teach:** C# basics vs C, MVVM in plain words, why replay mode matters for equipment software.

### M9 — Results, documentation, publish (no board)
- `docs/RESULTS.md`: every number with method (repeatability, accuracy vs caliper, PASS/FAIL table, bit-exact counts, golden vs OpenCV, frame rate, latency, resources, timing, power estimate). Never invent numbers.
- README in plain language (see previous project's final README style), block diagram (black & white, `make_diagram.py`), GIF from the demo video, YouTube link, limits section.
- Journal-style explainer (like the previous project's paper page) for the user to learn from.
- CV bullets + LinkedIn draft (in `docs/PORTFOLIO.md`), linking both projects.
- Final `rtl-reviewer` pass; fix or document findings in `docs/CDC.md` "Known limits".
- Make the repo public (the user clicks), add About text/topics, GitHub Release with BOOT.bin.
- **Model:** `sonnet`/`low` for writing; `opus`/`high` for the final review.

---

## 6. Technical notes and risks

- **Camera picture is not square to the table** → sizes change across the window. Mitigation: phone parallel to the table (use a level app), measure near the centre, calibrate at the centre, report the error by position (B3 item 1).
- **Phone app auto-exposure/auto-focus** changes brightness → Otsu (M6.3) or lock exposure; keep the lamp fixed.
- **Laptop overlays/UI on the camera picture** (buttons, notifications) → keep the window in the centre; turn on "do not disturb".
- **HDMI is 60 Hz but the phone stream may be 30 fps** (each camera frame shown twice) → results repeat; mention it in RESULTS (the FPGA still processes every HDMI frame).
- **Accumulator overflow** → widths from MEASUREMENT.md, asserted in the golden model; test with a fully black window.
- **CDC of a wide result set** → two banks + synchronized ready-bank bit; never let the ARM read a bank that is being written.
- **Histogram read-modify-write hazard** → a new pixel arrives every clock, so there is no time to read, add and write one bin before the next pixel; when two close pixels hit the same bin, forward the not-yet-written count (forwarding of the last 1–2 bins).
- **Board time** → MVP first; record data early; spare session B5.
- **Vitis build flakiness** → reuse `build_sw.py` with its fallback; kill leftover `vitis`/`java` processes holding `fpga_ws` if a build locks.

## 7. Board session checklist (copy into PROGRESS.md before each session)
1. Bitstream + ELF built today, sims passed, timing met (state the commit hash).
2. Laptop: display 1280×720@60 (duplicate), camera app full screen, do-not-disturb on, PuTTY/`uart_log.py` ready on the right COM port.
3. Board: boot jumper JTAG (or SD for the final demo), USB + both HDMI cables, power on; LD2 on = HDMI locked.
4. Camera: stand height, lamp position, paper — same as the written setup notes.
5. Program (`program.tcl all inspect`) or boot from SD.
6. Run the planned tests in order; save every log with a clear file name; take photos.
7. After: note results, problems, hours used, board days left in PROGRESS.md; commit.

## 8. Target CV bullets (fill with real numbers at the end)
- Built a real-time machine-vision inspection station on a Zynq-7010: hand-written SystemVerilog measures parts from live 720p60 camera video with no frame buffer (… ns latency, 60 FPS, 0 skipped frames).
- Verified the streaming hardware bit-exactly against a Python model on … real camera frames, and the model against OpenCV.
- Measured repeatability (… mm std. dev.) and accuracy (… mm mean error vs caliper), with PASS/FAIL correct on …/… parts; Otsu auto-threshold kept results stable under lighting changes.
- Wrote a C# WPF operator app (live UART + replay) with yield, trend chart and CSV logging.
