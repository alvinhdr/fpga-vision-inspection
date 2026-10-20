"""
evidence.py - guided evidence recording on the board (B2/B3): repeatability, accuracy, PASS/FAIL test.
Project: Real-Time FPGA Vision Inspection Station

It sets the board (threshold, calibration, nominal), then asks for each placement in turn. You place the part,
take your hand away, press Enter; the tool logs the board's result lines for a few seconds and writes them to
data/runs/<date>_evidence.csv with the part name, class (good/bad) and placement number.

  .\\.venv\\Scripts\\python.exe py\\evidence.py COM11
Plan (about 8 minutes): repeatability = bolt_good_01 NOT touched for 3 x 10 s at 3 positions;
accuracy / PASS-FAIL = each of the 5 good bolts and 4 bad parts, 3 placements x 3 s.
"""
import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uart_log import COLUMNS, parse_line  # noqa: E402

PARTS = [("bolt_good_01", "good"), ("bolt_good_02", "good"), ("bolt_good_03", "good"), ("bolt_good_04", "good"),
         ("bolt_good_05", "good"), ("bad_a", "bad"), ("bad_b", "bad"), ("bad_c", "bad"), ("bad_d", "bad")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("--t", type=int, default=130)
    ap.add_argument("--k", type=float, default=0.1728)
    ap.add_argument("--nom", type=float, default=11.6)
    ap.add_argument("--tol", type=float, default=1.0)
    ap.add_argument("--out", default=os.path.join("data", "runs", time.strftime("%Y%m%d") + "_evidence.csv"))
    args = ap.parse_args()
    import serial
    ser = serial.Serial(args.port, 115200, timeout=0.2)
    for c in (f"t {args.t}", f"c {args.k}", f"n {args.nom} {args.tol}", "o 1", "m 1"):
        ser.write((c + "\r\n").encode())
        time.sleep(0.15)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    new = not os.path.exists(args.out)
    fh = open(args.out, "a", newline="")
    wr = csv.writer(fh)
    if new:
        wr.writerow(["group", "part", "class", "placement"] + COLUMNS)

    def log(group, part, cls, placement, seconds):
        time.sleep(1.0)                         # hand away, picture settles
        ser.reset_input_buffer()
        n, t_end = 0, time.time() + seconds
        while time.time() < t_end:
            f = parse_line(ser.readline().decode("ascii", "replace"))
            if f:
                wr.writerow([group, part, cls, placement, f"{time.time():.3f}"] + f)
                n += 1
        fh.flush()
        print(f"   logged {n} lines")

    print(f"Board set: T={args.t}, k={args.k} mm/px, nominal {args.nom} +- {args.tol} mm. Output: {args.out}\n")
    print("PART 1 - REPEATABILITY: bolt_good_01 must NOT be touched between the 10 s recordings of one position.")
    for pos in (1, 2, 3):
        input(f"[repeat {pos}/3] Put bolt_good_01 at a NEW position inside the window (a different place and angle each time), "
              f"hand away, press Enter: ")
        log("repeat", "bolt_good_01", "good", pos, 10)

    print("\nPART 2 - ACCURACY and PASS/FAIL: 3 placements per part, 3 seconds each.")
    for part, cls in PARTS:
        for pl in (1, 2, 3):
            input(f"[{part} ({cls}) placement {pl}/3] Put ONLY this part in the window (new place / angle), hand away, press Enter: ")
            log("acc", part, cls, pl, 3)
    input("\nEmpty mat test: remove everything, hand away, press Enter: ")
    log("empty", "empty", "none", 1, 5)
    ser.write(b"s\r\n")
    t_end = time.time() + 1.5
    while time.time() < t_end:
        ln = ser.readline().decode("ascii", "replace").strip()
        if ln.startswith("S,"):
            print(ln)
    fh.close()
    print("DONE:", args.out)


if __name__ == "__main__":
    main()
