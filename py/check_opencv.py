"""
check_opencv.py - independent cross-check of py/golden.py with OpenCV (docs/MEASUREMENT.md section 7).
Project: Real-Time FPGA Vision Inspection Station

For every frame, the same gray window goes through OpenCV functions and must give exactly the
golden values: threshold mask, 3x3 majority filter, raw moments m00..m11, bounding box, histogram.
Also checks gray_hw against cv2.cvtColor (difference is reported, not an error: different rounding).

Usage:
  .\\.venv\\Scripts\\python.exe py\\check_opencv.py data\\raw\\s1 --t 120
  .\\.venv\\Scripts\\python.exe py\\check_opencv.py data\\raw\\s1 --t 180 --pol 1 --filt 0
Exit code 0 = all frames agree.
"""
import argparse
import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden import Settings, BBOX_EMPTY_MIN, BBOX_EMPTY_MAX, gray_hw, measure_frame  # noqa: E402


def opencv_measure(gray_win, s):
    if s.pol:
        _, obj = cv2.threshold(gray_win, s.t, 1, cv2.THRESH_BINARY)          # gray > T -> 1
    else:
        _, obj = cv2.threshold(gray_win, s.t - 1, 1, cv2.THRESH_BINARY_INV)  # gray <= T-1, i.e. gray < T
        if s.t == 0:
            obj[:] = 0
    if s.filt_en:
        cnt = cv2.filter2D(obj, cv2.CV_16S, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT)
        f = (cnt >= 5).astype(np.uint8)
    else:
        f = obj
    m = cv2.moments(f, binaryImage=True)
    r = {"A": int(m["m00"]), "SX": int(m["m10"]), "SY": int(m["m01"]),
         "SXX": int(m["m20"]), "SYY": int(m["m02"]), "SXY": int(m["m11"])}
    if r["A"]:
        x, y, w, h = cv2.boundingRect(f)
        r.update(UMIN=x, UMAX=x + w - 1, VMIN=y, VMAX=y + h - 1)
    else:
        r.update(UMIN=BBOX_EMPTY_MIN, UMAX=BBOX_EMPTY_MAX, VMIN=BBOX_EMPTY_MIN, VMAX=BBOX_EMPTY_MAX)
    hist = cv2.calcHist([gray_win], [0], None, [256], [0, 256]).ravel().astype(np.int64)
    return r, obj, f, hist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--t", type=int, default=120)
    ap.add_argument("--pol", type=int, default=1)
    ap.add_argument("--filt", type=int, default=1)
    ap.add_argument("--win", type=int, nargs=4, default=(400, 240, 480, 360))
    args = ap.parse_args()
    s = Settings(*args.win, t=args.t, pol=args.pol, filt_en=args.filt)
    files = sorted(glob.glob(os.path.join(args.folder, "*.png")))
    bad = 0
    gray_diff_max = 0
    for fn in files:
        bgr = cv2.imread(fn)
        g, gw, gobj, gf = measure_frame(bgr, s, with_hist=True, return_mask=True)
        o, oobj, of, ohist = opencv_measure(gw, s)
        errs = []
        if not np.array_equal(gobj, oobj):
            errs.append("threshold mask")
        if not np.array_equal(gf, of):
            errs.append("filter")
        for k in o:
            if g[k] != o[k]:
                errs.append(f"{k} golden {g[k]} opencv {o[k]}")
        if not np.array_equal(g["HIST"], ohist):
            errs.append("histogram")
        cvg = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(int)
        gray_diff_max = max(gray_diff_max, int(np.abs(cvg - gray_hw(bgr).astype(int)).max()))
        if errs:
            bad += 1
            print(os.path.basename(fn), "MISMATCH:", "; ".join(errs))
    print(f"{len(files)} frames, T={s.t} POL={s.pol} FILT={s.filt_en} window={args.win}: "
          f"{len(files) - bad} agree, {bad} differ. "
          f"(info: max |gray_hw - cv2.cvtColor| = {gray_diff_max})")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
