"""
show_camera_fullscreen.py - show a camera picture full screen at 1280x720, with NO menus.
Project: Real-Time FPGA Vision Inspection Station

This is the picture that goes over HDMI into the Zybo. The laptop display must be 1280x720.
Keys: q / ESC = quit,  s = save one PNG to data/raw/<session>/ (same as capture_frames.py),
      c = toggle a thin centre cross (for aiming the phone; only on the laptop copy, NOT in saved files)

Usage (PowerShell, repo root):
  .\\.venv\\Scripts\\python.exe py\\show_camera_fullscreen.py --list
  .\\.venv\\Scripts\\python.exe py\\show_camera_fullscreen.py 1 --session b1 --label bolt_good
"""
import argparse
import os
import time

import cv2

W, H = 1280, 720


def open_cam(index):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    return cap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("index", nargs="?", type=int, default=0)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--session", default=time.strftime("%Y%m%d"))
    ap.add_argument("--label", default="frame")
    args = ap.parse_args()

    if args.list:
        for i in range(6):
            cap = open_cam(i)
            ok, fr = cap.read()
            if ok:
                print(f"camera {i}: {fr.shape[1]}x{fr.shape[0]}  brightness {fr.mean():.0f}")
            cap.release()
        return

    cap = open_cam(args.index)
    out = os.path.join("data", "raw", args.session)
    os.makedirs(out, exist_ok=True)
    n = len([x for x in os.listdir(out) if x.startswith(args.label + "_")])
    win = "camera"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cross = False
    while True:
        ok, fr = cap.read()
        if not ok:
            time.sleep(0.05)
            continue
        if fr.shape[:2] != (H, W):
            fr = cv2.resize(fr, (W, H), interpolation=cv2.INTER_AREA)
        view = fr
        if cross:
            view = fr.copy()
            cv2.drawMarker(view, (W // 2, H // 2), (0, 255, 255), cv2.MARKER_CROSS, 40, 1)
        cv2.imshow(win, view)
        k = cv2.waitKey(1) & 0xFF
        if k in (ord("q"), 27):
            break
        if k == ord("s"):
            name = f"{args.label}_{n:03d}.png"
            cv2.imwrite(os.path.join(out, name), fr)
            print("saved", os.path.join(out, name))
            n += 1
        if k == ord("c"):
            cross = not cross
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
