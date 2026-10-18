"""
capture_frames.py - save labelled 1280x720 PNG frames for the golden model and the tests.
Project: Real-Time FPGA Vision Inspection Station

Two sources:
  --source screen   what the HDMI output will contain: the laptop screen (camera app full screen)
  --source cam N    a camera that OpenCV can open (laptop webcam, or the DroidCam virtual camera)
  --list-cams       show which camera numbers work and their size

Keys in the preview window:   SPACE = save one frame    b = save a burst (--burst frames)
                              q / ESC = quit
Files go to data/raw/<session>/<label>_<NNN>.png (data/raw is git-ignored; copy <= 20 frames to
data/sample/ by hand to commit them). A frames.csv in the same folder records every file.

Examples (PowerShell, repo root):
  .\\.venv\\Scripts\\python.exe py\\capture_frames.py --list-cams
  .\\.venv\\Scripts\\python.exe py\\capture_frames.py --source cam 1 --session s1 --label bolt_good
  .\\.venv\\Scripts\\python.exe py\\capture_frames.py --source screen --session s1 --label empty
"""
import argparse
import csv
import os
import time

import cv2
import numpy as np

W, H = 1280, 720


def open_cam(index):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    return cap


def list_cams(max_index=6):
    for i in range(max_index):
        cap = open_cam(i)
        ok, frame = cap.read()
        if ok:
            h, w = frame.shape[:2]
            print(f"camera {i}: works, {w}x{h}, mean brightness {frame.mean():.0f}")
        cap.release()


class ScreenGrabber:
    def __init__(self):
        import mss
        self.sct = mss.mss()
        mon = self.sct.monitors[1]            # primary monitor
        self.region = {"left": mon["left"], "top": mon["top"], "width": W, "height": H}

    def read(self):
        img = np.array(self.sct.grab(self.region))   # BGRA
        return True, cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


class CamGrabber:
    def __init__(self, index):
        self.cap = open_cam(index)

    def read(self):
        ok, frame = self.cap.read()
        if ok and frame.shape[:2] != (H, W):
            frame = cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)
        return ok, frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["screen", "cam"], default="cam")
    ap.add_argument("cam_index", nargs="?", type=int, default=0)
    ap.add_argument("--list-cams", action="store_true")
    ap.add_argument("--session", default=time.strftime("%Y%m%d"))
    ap.add_argument("--label", default="frame", help="e.g. bolt_good, bolt_bad, empty, nut_good")
    ap.add_argument("--burst", type=int, default=30)
    ap.add_argument("--outdir", default=os.path.join("data", "raw"))
    args = ap.parse_args()

    if args.list_cams:
        list_cams()
        return

    grab = ScreenGrabber() if args.source == "screen" else CamGrabber(args.cam_index)
    out = os.path.join(args.outdir, args.session)
    os.makedirs(out, exist_ok=True)
    csv_path = os.path.join(out, "frames.csv")
    new_csv = not os.path.exists(csv_path)
    f = open(csv_path, "a", newline="")
    wr = csv.writer(f)
    if new_csv:
        wr.writerow(["file", "label", "source", "time"])

    n = len([x for x in os.listdir(out) if x.startswith(args.label + "_")])

    def save(frame):
        nonlocal n
        name = f"{args.label}_{n:03d}.png"
        cv2.imwrite(os.path.join(out, name), frame)
        wr.writerow([name, args.label, args.source, time.strftime("%H:%M:%S")])
        f.flush()
        n += 1

    print(f"Saving to {out}  label={args.label}.  SPACE=save  b=burst({args.burst})  q=quit")
    while True:
        ok, frame = grab.read()
        if not ok:
            print("no frame"); time.sleep(0.1); continue
        view = frame.copy()
        cv2.putText(view, f"{args.label} saved:{n}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("capture (SPACE/b/q)", cv2.resize(view, (W // 2, H // 2)))
        k = cv2.waitKey(1) & 0xFF
        if k == ord(" "):
            save(frame)
        elif k == ord("b"):
            for _ in range(args.burst):
                ok, fr = grab.read()
                if ok:
                    save(fr)
        elif k in (ord("q"), 27):
            break
    f.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
