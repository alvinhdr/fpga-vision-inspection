"""
golden.py - integer golden model of the per-frame measurement (docs/MEASUREMENT.md sections 1-5).
Project: Real-Time FPGA Vision Inspection Station

This file IS the reference for the RTL: every value must match the hardware bit-exactly.
Integer NumPy only (no floats) in everything that the RTL computes.

Use as a module:
    from golden import Settings, gray_hw, measure_frame
    res = measure_frame(bgr_image, Settings(t=120))
Or from the command line, one CSV line per frame:
    .\\.venv\\Scripts\\python.exe py\\golden.py data\\raw\\s1 --t 120 --out build\\golden_s1.csv
"""
import argparse
import csv
import glob
import os
from dataclasses import dataclass

import numpy as np

FRAME_W, FRAME_H = 1280, 720

# Register widths (docs/MEASUREMENT.md section 5), asserted for every frame
WIDTH = {"A": 20, "SX": 30, "SY": 29, "SXX": 39, "SYY": 38, "SXY": 38}
BBOX_EMPTY_MIN = 0x7FF          # UMIN/VMIN when no object pixel
BBOX_EMPTY_MAX = 0              # UMAX/VMAX when no object pixel


@dataclass
class Settings:
    x0: int = 400               # default window (MEASUREMENT.md section 1)
    y0: int = 240
    w: int = 480
    h: int = 360
    t: int = 120                # threshold
    pol: int = 1                # 1 = object brighter than T, 0 = darker
    filt_en: int = 1            # 3x3 majority filter on/off

    def check(self):
        assert 1 <= self.w and 1 <= self.h, "window size must be >= 1"
        assert 0 <= self.x0 and self.x0 + self.w <= FRAME_W, "window outside frame (x)"
        assert 0 <= self.y0 and self.y0 + self.h <= FRAME_H, "window outside frame (y)"
        assert 0 <= self.t <= 255 and self.pol in (0, 1) and self.filt_en in (0, 1)


def gray_hw(bgr):
    """gray = (77R + 150G + 29B) >> 8, same as rtl/rgb2gray.sv. Input: OpenCV BGR uint8 image."""
    b = bgr[:, :, 0].astype(np.uint32)
    g = bgr[:, :, 1].astype(np.uint32)
    r = bgr[:, :, 2].astype(np.uint32)
    return ((77 * r + 150 * g + 29 * b) >> 8).astype(np.uint8)


def object_mask(gray_win, s):
    """MEASUREMENT.md section 3. gray_win = window crop. Returns uint8 0/1."""
    return (gray_win > s.t).astype(np.uint8) if s.pol else (gray_win < s.t).astype(np.uint8)


def majority3(obj):
    """MEASUREMENT.md section 4: 1 if >= 5 of the 3x3 neighbours are 1; outside the window counts as 0."""
    p = np.pad(obj, 1).astype(np.uint8)
    h, w = obj.shape
    cnt = np.zeros((h, w), np.uint8)
    for dy in range(3):
        for dx in range(3):
            cnt += p[dy:dy + h, dx:dx + w]
    return (cnt >= 5).astype(np.uint8)


def accumulate(f):
    """MEASUREMENT.md section 5. f = filtered 0/1 window mask. Python ints (exact)."""
    vs, us = np.nonzero(f)
    us = us.astype(np.int64)
    vs = vs.astype(np.int64)
    r = {
        "A": int(len(us)),
        "SX": int(us.sum()), "SY": int(vs.sum()),
        "SXX": int((us * us).sum()), "SYY": int((vs * vs).sum()), "SXY": int((us * vs).sum()),
    }
    if r["A"]:
        r.update(UMIN=int(us.min()), UMAX=int(us.max()), VMIN=int(vs.min()), VMAX=int(vs.max()))
    else:
        r.update(UMIN=BBOX_EMPTY_MIN, UMAX=BBOX_EMPTY_MAX, VMIN=BBOX_EMPTY_MIN, VMAX=BBOX_EMPTY_MAX)
    for k, bits in WIDTH.items():
        assert 0 <= r[k] < (1 << bits), f"{k} = {r[k]} does not fit in {bits} bits"
    return r


def measure_frame(bgr, s=None, with_hist=False, return_mask=False):
    """Whole per-frame measurement of one 1280x720 BGR frame."""
    s = s or Settings()
    s.check()
    assert bgr.shape[:2] == (FRAME_H, FRAME_W), f"frame must be {FRAME_W}x{FRAME_H}"
    gray_win = gray_hw(bgr)[s.y0:s.y0 + s.h, s.x0:s.x0 + s.w]
    obj = object_mask(gray_win, s)
    f = majority3(obj) if s.filt_en else obj
    r = accumulate(f)
    if with_hist:
        r["HIST"] = np.bincount(gray_win.ravel(), minlength=256).astype(np.int64)
    if return_mask:
        return r, gray_win, obj, f
    return r


FIELDS = ["A", "SX", "SY", "SXX", "SYY", "SXY", "UMIN", "UMAX", "VMIN", "VMAX"]


def main():
    import cv2
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--t", type=int, default=120)
    ap.add_argument("--pol", type=int, default=1)
    ap.add_argument("--filt", type=int, default=1)
    ap.add_argument("--win", type=int, nargs=4, metavar=("X0", "Y0", "W", "H"), default=(400, 240, 480, 360))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    s = Settings(*args.win, t=args.t, pol=args.pol, filt_en=args.filt)
    files = sorted(glob.glob(os.path.join(args.folder, "*.png")))
    out = open(args.out, "w", newline="") if args.out else None
    wr = csv.writer(out) if out else None
    if wr:
        wr.writerow(["file"] + FIELDS)
    for fn in files:
        r = measure_frame(cv2.imread(fn), s)
        row = [os.path.basename(fn)] + [r[k] for k in FIELDS]
        if wr:
            wr.writerow(row)
        else:
            print(*row, sep=",")
    if out:
        out.close()
        print(f"{len(files)} frames -> {args.out}")


if __name__ == "__main__":
    main()
