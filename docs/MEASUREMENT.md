# MEASUREMENT — integer specification of the per-frame measurement

This file is the **specification**. `py/golden.py` implements it in integer NumPy, the RTL (M4) must match
`py/golden.py` **bit-exactly**, and `py/check_opencv.py` checks the golden model against OpenCV.
If the RTL and this file disagree, this file wins (or is changed first, with a reason).

Written 2026-10-18 (M2), based on the 285 frames of session `s1` (`data/raw/s1/`, see `notes/PROGRESS.md`).

---

## 1. Coordinates

- Frame: 1280 x 720, `x` = column 0..1279 (left to right), `y` = row 0..719 (top to bottom).
  Counted from DE only (`pix_pos_counter.sv`), first visible pixel = (0, 0).
- **Inspection window**: `x0, y0` (top-left corner) and `W, H` (size), registers set by the ARM.
  Inside the window the coordinates are **relative**: `u = x - x0` (0..W-1), `v = y - y0` (0..H-1).
  All accumulators use `u, v`, never `x, y` (smaller numbers, and the result does not depend on where the window is).
- Limits: `1 <= W`, `1 <= H`, `x0 + W <= 1280`, `y0 + H <= 720`. The ARM must only write legal values;
  the RTL clamps nothing (documented limit, checked in software).
- **Default window** (chosen from the s1 frames): `x0 = 400, y0 = 240, W = 480, H = 360` -> x 400..879, y 240..599.
  Reasons: all parts of s1 lie in x 519..748, y 246..472; the tripod leg starts at x = 962 in every frame;
  a fixed dust grain on the mat at (679, 218) is above the window.

## 2. Gray value (same as `rtl/rgb2gray.sv`)

```
gray = (77*R + 150*G + 29*B) >> 8          (R, G, B = 8-bit, result 0..255)
```
Note: OpenCV's `cvtColor(BGR2GRAY)` uses other fixed-point weights and rounding, so it can differ by 1.
The golden model uses **our** formula; the OpenCV cross-check starts from the same gray image.

## 3. Object pixel (threshold with polarity)

```
POL = 1 (bright part on dark background, our setup):  obj(u,v) = gray > T
POL = 0 (dark part on light background):              obj(u,v) = gray < T
```
`T` = 8-bit register. Outside the window `obj = 0`.
Measured on s1 (window above, after the filter of section 4): empty mat gives 0 object pixels at
`T >= 120` (dark frames, mean gray 12..26) and at `T >= 180` (bright frames, mean gray 53..57).
**Otsu was tested on these frames and rejected** for the MVP: it chose T = 18..75 on dark frames (the part
is under 1 % of the window, so Otsu splits the mat noise instead). An automatic threshold is Standard tier
and must be chosen from data first.

## 4. 3 x 3 majority filter (speck removal)

```
cnt(u,v)  = sum of obj over the 3x3 neighbourhood centred on (u,v)   (neighbours outside the window count as 0)
f(u,v)    = 1 if cnt >= 5 else 0          when FILT_EN = 1
f(u,v)    = obj(u,v)                      when FILT_EN = 0
```
Why it is in the MVP (it was Standard tier in PLAN.md): the fuzzy mat gives single bright pixels; on the bright
frames the filter cut empty-window object pixels from 1,973..2,186 to 101..137 at T = 120, and from 33..42 to
2..6 at T = 160, while a bolt keeps almost all its pixels. RTL: two 1-bit line buffers of W bits (BRAM).
Specks bigger than about 3 x 3 (real dust) are NOT removed: keep the mat clean.

## 5. Per-frame accumulators (over the filtered pixels `f`)

| Name | Definition | Max value (W=1280, H=720, all pixels set) | Bits needed | Register |
|---|---|---|---|---|
| `A`   | Σ f | 921,600 | 20 | 32 |
| `SX`  | Σ f·u | 589,363,200 | 30 | 32 |
| `SY`  | Σ f·v | 331,315,200 | 29 | 32 |
| `SXX` | Σ f·u² | 502,726,809,600 | 39 | 40 (two 32-bit words) |
| `SYY` | Σ f·v² | 158,920,857,600 | 38 | 40 (two words) |
| `SXY` | Σ f·u·v | 211,876,070,400 | 38 | 40 (two words) |
| `UMIN, UMAX, VMIN, VMAX` | min/max of u and v where f = 1 | 1279 / 719 | 11 / 10 | 16 each |
| `HIST[g]` (Standard tier) | number of window pixels with gray = g (all pixels, not only f) | 921,600 | 20 | 32 |

The widths are chosen for the **largest legal window** (the whole frame), so no setting can overflow.
`py/golden.py` asserts every width. Products: `u²` is 11 x 11 bits, `u·v` is 11 x 10 bits (one DSP48 each).

Empty window (`A = 0`): `SX..SXY = 0`, and the bounding box reads `UMIN = VMIN = 0x7FF`, `UMAX = VMAX = 0`
(the reset values). The ARM must check `A` first and never divide by it when it is 0.

**Timing:** all accumulators are cleared at the start of the frame (first visible pixel, before any window pixel) and the
complete set is copied into one of two result banks after the last window pixel has passed the filter
(the filter output for row H-1 comes one row and one pixel later). The results of frame N are therefore used
(by the ARM and the overlay) during frame N+1. Bank handling and the clock crossing are specified in M4 (`docs/CDC.md`).

## 6. Per-frame maths on the ARM (floating point, `double`)

```
cx  = SX / A,   cy = SY / A                        centroid (window coords; + x0, y0 for frame coords)
m20 = SXX / A - cx²,  m02 = SYY / A - cy²,  m11 = SXY / A - cx·cy      central second moments (px²)
l1, l2 = (m20 + m02)/2 ± sqrt( ((m20 - m02)/2)² + m11² )               l1 >= l2 >= 0
theta  = 0.5 · atan2(2·m11, m20 - m02)              angle of the long axis, radians
                                                   (image y points down: positive = clockwise on screen)
L_px   = sqrt(12·l1 + 1),   W_px = sqrt(12·l2 + 1)  length and width of the "equivalent rectangle"
```
Why `sqrt(12·l + 1)`: a straight line of `n` pixels has variance `(n² - 1) / 12`, so a solid axis-aligned
rectangle of `n x m` pixels gives exactly `L_px = n`, `W_px = m`. For a bolt (head wider than the shank) it is
an *equivalent* length, close to but not exactly the head-to-tip length; it uses every pixel, so it is far
more repeatable than an edge measurement, and it does not depend on the angle.
The axis-aligned bounding box (`UMAX - UMIN + 1`, `VMAX - VMIN + 1`) is used for drawing and as a sanity check.

**Millimetres** (software only): `L_mm = L_px · k`, `W_mm = W_px · k`, with `k` = mm per pixel from a calibration
(a reference object of known size, or a ruler in the picture). Pixels are never converted in hardware.

**Decision** (order matters):
1. `A < A_MIN` -> `NOPART`.
2. bounding box touches the window edge (`UMIN = 0` or `VMIN = 0` or `UMAX = W-1` or `VMAX = H-1`) -> `EDGE`
   (part not fully inside: no decision).
3. **box ratio** `= (bbox_w · bbox_h) / ((L_px + W_px)² / 2)` > 1.5 -> `NOISY` (no decision).
   One compact part fills about the box its equivalent rectangle needs at the worst angle (45°); a speck far
   from the part makes the box much bigger, and also spoils the second moments (one s1 frame: L_px 158 instead
   of about 73). Limit 1.5 chosen on session s1: flags 32 of 244 part frames, including every frame with a
   clearly too-large box. Software only, no RTL.
4. `|L_mm - L_nom| <= L_tol` and `|W_mm - W_nom| <= W_tol` -> `PASS`, else `FAIL`.

## 7. What the golden model is checked against

`py/check_opencv.py`, for every frame: `cv2.threshold` (THRESH_BINARY, same T) = our object mask;
3x3 sum with `cv2.filter2D` (constant 0 border) >= 5 = our filter; `cv2.moments(f, binaryImage=True)`
m00, m10, m01, m20, m02, m11 = `A, SX, SY, SXX, SYY, SXY` (exact: all values are integers below 2^53);
`cv2.boundingRect(f)` = our bounding box; `cv2.calcHist` = our histogram.

## 8. Known limits (honest list)

- Shiny metal: the threads give bright highlights and dark gaps, so at high T a bolt falls apart into pieces.
  The moments still add up all pieces, which is fine for one part in the window.
- One part in the window. Two parts, a hand, or dust are added together (no connected components; stretch goal).
- The equivalent length depends a little on the part's shape (head size); calibrating with the same part type
  removes most of this. Accuracy is limited by the ruler (1 mm marks) used as the reference.
- Lighting: a fixed `T` only works for one lighting condition (see section 3). Lock the camera exposure.
- Shiny round parts show a bright stripe along the middle and dark edges, so `W_px` measures the stripe, not
  the real width (s1 good bolts: W_px about 10 px, about 1.4 mm with the provisional calibration, which is too
  thin for a real bolt shank). Length is much less affected. Diffuse light would help.
- Second moments are sensitive to far outliers (specks): hence the 3x3 filter, the NOISY check, and a clean mat.

## 9. First offline results on session s1 (2026-10-18, `py/measure.py data/raw/s1 --report`)

Settings: default window, filter on, T = 120 (dark frames) / 180 (bright frames). Median and MAD (median
absolute deviation) over the frames with status MEASURED.

| Part | frames used | L_px median (MAD) | W_px median (MAD) |
|---|---|---|---|
| good bolts 01..05 | 21, 26, 24, 18, 22 | 71.0 .. 73.6 (1.8 .. 3.1) | 8.6 .. 11.4 |
| bad_d | 30 | 84.3 (4.9) | 13.1 |
| bad_c | 30 | 104.5 (12.8) | 14.3 |
| bad_b | 11 (16 NOISY) | 149.3 (11.0) | 23.9 |
| bad_a | 30 | 194.9 (14.3) | 28.4 |

- Golden model = OpenCV on all 285 frames, 5 settings; 3 planted bugs were each caught on 10/10 frames.
- The good bolts are separated from every bad type by length alone (closest: bad_d, 84 vs 73 px).
- Noise between 3 frames of the same placement (0.25 s apart): median std of L_px = 1.33 px.
- **Not yet a fair test**: all good bolts are in the dark frames and all bad parts in the bright frames, with
  different thresholds; the bright threshold keeps only highlights, so the bad parts come out too short
  (provisional mm: bad_a 26.7 vs ruler about 30+, bad_b 20.5 vs about 25, bad_c 14.3 vs 15, bad_d 11.6 vs 13).
  A new capture with **one locked lighting** for all parts is needed before any accuracy claim.
- Provisional calibration only (k = 0.137 mm/px from "good bolt = about 10 mm"); a ruler-in-picture
  calibration replaces it.
