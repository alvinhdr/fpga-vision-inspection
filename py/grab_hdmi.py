"""
grab_hdmi.py - interactive frame grabber for the HDMI picture (second screen, 1280x720).
Project: Real-Time FPGA Vision Inspection Station

How to use: put the part on the mat, type a label, press Enter. The tool saves --n frames
(0.25 s apart) as data/raw/<session>/<label>_<NNN>.png and logs them in frames.csv.
Just press Enter on an empty line to repeat the last label (move the part a little first).
Type q to quit. Labels are free text, for example:
    empty            no part in the picture
    bolt_good_01     identical good bolt number 1
    bolt_bad_short   a bad bolt (shorter), nut_good_01, bolt_good_angle45 ...
Everything after the first underscore-separated words is up to you, keep it short.

Usage (PowerShell, repo root):
  .\\.venv\\Scripts\\python.exe py\\grab_hdmi.py --session s1
"""
import argparse
import csv
import os
import time

import cv2
import mss
import numpy as np

W, H = 1280, 720


def find_monitor(sct):
    """The board's output screen: the monitor that is exactly 1280x720."""
    for i, m in enumerate(sct.monitors[1:], start=1):
        if m["width"] == W and m["height"] == H:
            return m
    raise SystemExit("No 1280x720 screen found. Set the board's monitor to 1280x720 in Windows display settings.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=time.strftime("%Y%m%d"))
    ap.add_argument("--n", type=int, default=3, help="frames per Enter")
    ap.add_argument("--gap", type=float, default=0.25, help="seconds between frames")
    ap.add_argument("--outdir", default=os.path.join("data", "raw"))
    args = ap.parse_args()

    out = os.path.join(args.outdir, args.session)
    os.makedirs(out, exist_ok=True)
    csv_path = os.path.join(out, "frames.csv")
    new = not os.path.exists(csv_path)
    f = open(csv_path, "a", newline="")
    wr = csv.writer(f)
    if new:
        wr.writerow(["file", "label", "time", "gray_mean", "gray_max"])

    with mss.MSS() as sct:
        mon = find_monitor(sct)
        print(f"Grabbing screen at x={mon['left']} ({W}x{H}) -> {out}")
        last = None
        while True:
            s = input("label (Enter = repeat, q = quit): ").strip()
            if s.lower() == "q":
                break
            if s:
                last = s
            if not last:
                print("type a label first")
                continue
            for _ in range(args.n):
                img = np.array(sct.grab(mon))[:, :, :3]
                g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                k = len([x for x in os.listdir(out) if x.startswith(last + "_")])
                name = f"{last}_{k:03d}.png"
                cv2.imwrite(os.path.join(out, name), img)
                wr.writerow([name, last, time.strftime("%H:%M:%S"), f"{g.mean():.1f}", int(g.max())])
                f.flush()
                time.sleep(args.gap)
            total = len([x for x in os.listdir(out) if x.endswith(".png")])
            print(f"  saved {args.n} x '{last}'  (mean gray {g.mean():.1f}, total frames {total})")
    f.close()


if __name__ == "__main__":
    main()
