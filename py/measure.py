"""
measure.py - the ARM's per-frame maths (docs/MEASUREMENT.md section 6) in Python, plus an offline report.
Project: Real-Time FPGA Vision Inspection Station

The same formulas will be written in C for the ARM (M5); this file predicts their output on recorded frames.

  .\\.venv\\Scripts\\python.exe py\\measure.py --selftest
  .\\.venv\\Scripts\\python.exe py\\measure.py data\\raw\\s1 --report
Offline only: the threshold is picked per frame from the window brightness (dark set T=120, bright set T=180),
because session s1 has two lighting conditions. On the board, T is one register value.
"""
import argparse
import csv
import math
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden import Settings, measure_frame, accumulate  # noqa: E402


def frame_math(r, s, k_mm_per_px=None, a_min=50):
    """Accumulators r (dict from golden) -> geometry. Mirrors the C code of M5."""
    out = {"status": "NOPART"}
    A = r["A"]
    if A < a_min:
        return out
    cx = r["SX"] / A
    cy = r["SY"] / A
    m20 = r["SXX"] / A - cx * cx
    m02 = r["SYY"] / A - cy * cy
    m11 = r["SXY"] / A - cx * cy
    half = (m20 + m02) / 2
    d = math.sqrt(((m20 - m02) / 2) ** 2 + m11 ** 2)
    l1, l2 = half + d, max(half - d, 0.0)
    out.update(
        status="MEASURED",
        cx=cx + s.x0, cy=cy + s.y0,
        theta_deg=math.degrees(0.5 * math.atan2(2 * m11, m20 - m02)),
        L_px=math.sqrt(12 * l1 + 1), W_px=math.sqrt(12 * l2 + 1),
        bbox_w=r["UMAX"] - r["UMIN"] + 1, bbox_h=r["VMAX"] - r["VMIN"] + 1,
        edge=(r["UMIN"] == 0 or r["VMIN"] == 0 or r["UMAX"] == s.w - 1 or r["VMAX"] == s.h - 1),
    )
    # Box ratio (MEASUREMENT.md section 6, step 3): one compact part nearly fills the bounding box that its
    # equivalent rectangle L x W would need at the worst angle (45 deg: (L+W)^2 / 2). Far specks make the box
    # much bigger than that. Limit 1.5 chosen on session s1 (flags 32 of 244 part frames).
    L, Wd = out["L_px"], out["W_px"]
    out["box_ratio"] = (out["bbox_w"] * out["bbox_h"]) / ((L + Wd) ** 2 / 2)
    if k_mm_per_px:
        out["L_mm"] = out["L_px"] * k_mm_per_px
        out["W_mm"] = out["W_px"] * k_mm_per_px
    if out["edge"]:
        out["status"] = "EDGE"
    elif out["box_ratio"] > BOX_RATIO_MAX:
        out["status"] = "NOISY"
    return out


BOX_RATIO_MAX = 1.5


def selftest():
    """Solid rectangles of n x m pixels must give L_px = n and W_px = m exactly (any position)."""
    s = Settings()
    ok = True
    for (n, m, u0, v0) in [(60, 12, 100, 50), (1, 1, 5, 5), (200, 3, 0 + 1, 300), (37, 37, 200, 100)]:
        f = np.zeros((s.h, s.w), np.uint8)
        f[v0:v0 + m, u0:u0 + n] = 1          # n wide (u), m high (v)
        g = frame_math(accumulate(f), s, a_min=1)
        good = abs(g["L_px"] - max(n, m)) < 1e-9 and abs(g["W_px"] - min(n, m)) < 1e-9
        ok &= good
        print(f"rect {n}x{m}: L_px={g['L_px']:.6f} W_px={g['W_px']:.6f} theta={g['theta_deg']:.1f} -> {'OK' if good else 'FAIL'}")
    # rotated line: a 1-pixel-wide diagonal is NOT a rectangle; just print it
    f = np.zeros((s.h, s.w), np.uint8)
    for i in range(80):
        f[100 + i, 100 + i] = 1
    g = frame_math(accumulate(f), s, a_min=1)
    print(f"diagonal 80 px (info): L_px={g['L_px']:.2f} (80*sqrt2 = {80 * math.sqrt(2):.2f}), theta={g['theta_deg']:.1f} deg")
    print("SELFTEST", "PASSED" if ok else "FAILED")
    return ok


def report(folder):
    import cv2
    rows = list(csv.DictReader(open(os.path.join(folder, "frames.csv"))))
    hand_path = os.path.join(folder, "hand_frames.txt")
    hand = set(open(hand_path).read().split()) if os.path.exists(hand_path) else set()
    by = defaultdict(list)
    for r in rows:
        if r["file"] in hand:
            continue
        bgr = cv2.imread(os.path.join(folder, r["file"]))
        s = Settings()
        win = bgr[s.y0:s.y0 + s.h, s.x0:s.x0 + s.w]
        bright = win.mean() > 45
        s.t = 180 if bright else 120
        acc = measure_frame(bgr, s)
        g = frame_math(acc, s)
        g["file"], g["bright"], g["A"] = r["file"], bright, acc["A"]
        by[r["label"]].append(g)
    print(f"{'label':<14}{'n':>4} {'set':<12}{'NOPART':>7}{'EDGE':>5}{'NOISY':>6}{'used':>5}  "
          f"{'L_px med':>8} {'MAD':>4}  {'W_px med':>8} {'MAD':>4}  {'A med':>6}")
    summary = {}
    for lab in sorted(by):
        G = by[lab]
        M = [g for g in G if g["status"] == "MEASURED"]
        L = np.array([g["L_px"] for g in M]) if M else np.array([np.nan])
        W = np.array([g["W_px"] for g in M]) if M else np.array([np.nan])
        sets = {("bright" if g["bright"] else "dark") for g in G}
        cnt = {k: sum(g["status"] == k for g in G) for k in ("NOPART", "EDGE", "NOISY")}
        mad = lambda x: float(np.median(np.abs(x - np.median(x))))
        a_med = int(np.median([g["A"] for g in M])) if M else 0
        print(f"{lab:<14}{len(G):>4} {'/'.join(sorted(sets)):<12}{cnt['NOPART']:>7}{cnt['EDGE']:>5}{cnt['NOISY']:>6}{len(M):>5}  "
              f"{np.median(L):>8.1f} {mad(L):>4.1f}  {np.median(W):>8.1f} {mad(W):>4.1f}  {a_med:>6}")
        summary[lab] = (float(np.median(L)), mad(L), float(np.median(W)), mad(W), M)
    # PROVISIONAL mm: calibrated on the good bolts with the user's "about 10 mm" (ruler, +-1 mm).
    goods = [v for k, v in summary.items() if k.startswith("bolt_good")]
    if goods:
        good_L = float(np.median(np.concatenate([[g["L_px"] for g in v[4]] for v in goods])))
        k = 10.0 / good_L
        print(f"\nPROVISIONAL calibration: good bolt median L_px = {good_L:.1f} -> k = {k:.4f} mm/px "
              f"(assumes good bolt = 10 mm; the user's ruler estimate, +-1 mm -> k +-10 %)")
        for lab in sorted(summary):
            if lab.startswith("bad"):
                print(f"   {lab}: L about {summary[lab][0] * k:5.1f} mm, W about {summary[lab][2] * k:4.1f} mm (equivalent rectangle)")
    # repeatability: each Enter in grab_hdmi.py saved 3 frames of the SAME placement (0.25 s apart)
    spreads = []
    for lab, (_, _, _, _, M) in summary.items():
        if not lab.startswith("bolt_good"):
            continue
        M = sorted(M, key=lambda g: g["file"])
        for i in range(0, len(M) - 2, 3):
            trip = [g["L_px"] for g in M[i:i + 3]]
            if len({g["file"].rsplit('_', 1)[0] for g in M[i:i + 3]}) == 1:
                spreads.append(np.std(trip))
    if spreads:
        print(f"\nrepeatability (good bolts, std of L_px inside each 3-frame burst, {len(spreads)} bursts): "
              f"median {np.median(spreads):.2f} px, max {np.max(spreads):.2f} px")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="?")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if args.folder:
        report(args.folder)


if __name__ == "__main__":
    main()
