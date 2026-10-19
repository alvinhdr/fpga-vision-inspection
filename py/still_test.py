"""
still_test.py - ON THE BOARD: bit-exact check of the real hardware with recorded frames shown as still images.
Project: Real-Time FPGA Vision Inspection Station

Each recorded 1280x720 frame is shown full screen on the board's HDMI screen (the 1280x720 monitor). The HDMI
picture is then constant, so every result line the board sends must equal the golden model exactly:
A (pixels) exactly, and cx, cy, L_px, W_px, angle within the printed rounding.
This also proves that the laptop sends FULL-range RGB (limited range 16-235 would change A).

  .\\.venv\\Scripts\\python.exe py\\still_test.py COM16 --n 20
Needs: board programmed with the inspect bitstream + ARM program, window/threshold as in --t (default 120, the
ARM's start values), result lines on (m 1).
"""
import argparse
import glob
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden import Settings, measure_frame        # noqa: E402
from measure import frame_math                    # noqa: E402
from uart_log import parse_line                   # noqa: E402


def board_screen():
    import mss
    with mss.MSS() as s:
        for m in s.monitors[1:]:
            if m["width"] == 1280 and m["height"] == 720:
                return m["left"], m["top"]
    sys.exit("no 1280x720 screen (the board's output) found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("--folder", default=os.path.join("data", "raw", "s1"))
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--t", type=int, default=120)
    ap.add_argument("--settle", type=float, default=0.6, help="seconds to wait after showing a frame")
    args = ap.parse_args()
    import serial

    files = sorted(glob.glob(os.path.join(args.folder, "*.png")))
    files = [files[int(i)] for i in np.linspace(0, len(files) - 1, min(args.n, len(files)))]
    x, y = board_screen()
    win = "still"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.moveWindow(win, x, y)
    cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    ser = serial.Serial(args.port, 115200, timeout=0.2)
    ser.write(f"t {args.t}\r\nm 1\r\n".encode())
    s = Settings(t=args.t)
    ok = bad = 0
    for fn in files:
        img = cv2.imread(fn)
        cv2.imshow(win, img)
        cv2.waitKey(1)
        t_end = time.time() + args.settle
        while time.time() < t_end:
            cv2.waitKey(20)
        ser.reset_input_buffer()
        lines = []
        while len(lines) < 5:                       # 5 consecutive results of the still frame
            f = parse_line(ser.readline().decode("ascii", "replace"))
            if f:
                lines.append(f)
            cv2.waitKey(1)
        r = measure_frame(img, s)
        g = frame_math(r, s)
        errs = []
        for f in lines:
            a = int(f[2])
            if a != r["A"]:
                errs.append(f"A board {a} golden {r['A']}")
            elif g["status"] != "NOPART" and f[1] != "NOPART":
                for name, idx, ref, tol in (("cx", 3, g["cx"], 0.051), ("cy", 4, g["cy"], 0.051),
                                            ("L_px", 5, g["L_px"], 0.0051), ("W_px", 6, g["W_px"], 0.0051)):
                    if abs(float(f[idx]) - ref) > tol:
                        errs.append(f"{name} board {f[idx]} golden {ref:.3f}")
        name = os.path.basename(fn)
        if errs:
            bad += 1
            print(f"{name}: MISMATCH {errs[:3]}")
        else:
            ok += 1
            print(f"{name}: A={r['A']} OK (5 results)")
    cv2.destroyAllWindows()
    print(f"\nSTILL TEST: {ok}/{ok + bad} frames bit-exact on the board")
    sys.exit(0 if bad == 0 else 1)


if __name__ == "__main__":
    main()
