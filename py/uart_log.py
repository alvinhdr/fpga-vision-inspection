"""
uart_log.py - read the result lines of the ARM program (docs/PROTOCOL.md) and save them to a CSV.
Project: Real-Time FPGA Vision Inspection Station

  .\\.venv\\Scripts\\python.exe py\\uart_log.py COM16 --out data\\runs\\20261019_repeat_bolt.csv --seconds 20
  .\\.venv\\Scripts\\python.exe py\\uart_log.py --parse-test            (no board needed: tests the parser)
Typed command lines can be sent while logging with --send "t 120" "w 400 240 480 360" (sent once at the start).
Press Ctrl+C to stop. The CSV has a PC time column and one column per field; bad lines are counted, not saved.
"""
import argparse
import csv
import os
import sys
import time

COLUMNS = ["pc_time", "frame", "status", "A_px", "cx", "cy", "L_px", "W_px", "angle_deg", "L_mm", "W_mm", "verdict"]
STATUSES = {"NOPART", "EDGE", "NOISY", "MEASURED"}
VERDICTS = {"PASS", "FAIL", "NOCAL", "NONE"}


def parse_line(line):
    """Return the 11 fields of a valid R line (without the leading R), else None."""
    line = line.strip()
    if not line.startswith("R,"):
        return None
    p = line.split(",")
    if len(p) != 12 or p[2] not in STATUSES or p[11] not in VERDICTS:
        return None
    try:
        int(p[1]); int(p[3])
        for v in p[4:11]:
            float(v)
    except ValueError:
        return None
    return p[1:]


def parse_test():
    good = "R,1234,MEASURED,325,640.2,350.1,72.98,10.45,-87.9,10.00,1.43,PASS"
    cases = {
        good: True,
        "R,1,NOPART,0,0.0,0.0,0.00,0.00,0.0,0.00,0.00,NONE": True,
        "# comment": False,
        "R,1234,MEASURED,325,640.2,350.1,72.98,10.45,-87.9,10.00,1.43": False,   # too short
        "R,12x4,MEASURED,325,640.2,350.1,72.98,10.45,-87.9,10.00,1.43,PASS": False,
        "R,1234,WEIRD,325,640.2,350.1,72.98,10.45,-87.9,10.00,1.43,PASS": False,
        "S,id=0x1a570001": False,
        "": False,
    }
    bad = 0
    for line, ok in cases.items():
        if (parse_line(line) is not None) != ok:
            print("PARSE TEST FAILED for:", repr(line)); bad += 1
    print("parse test:", "PASSED" if not bad else f"{bad} FAILED")
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--out", default=None)
    ap.add_argument("--seconds", type=float, default=0, help="0 = until Ctrl+C")
    ap.add_argument("--send", nargs="*", default=[])
    ap.add_argument("--parse-test", action="store_true")
    args = ap.parse_args()
    if args.parse_test:
        sys.exit(0 if parse_test() else 1)
    if not args.port:
        sys.exit("give the COM port, for example COM16")
    import serial
    out = args.out or os.path.join("data", "runs", time.strftime("%Y%m%d_%H%M%S") + ".csv")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    ser = serial.Serial(args.port, args.baud, timeout=0.2)
    for c in args.send:
        ser.write((c + "\r\n").encode()); time.sleep(0.1)
    good = bad = 0
    t_end = time.time() + args.seconds if args.seconds else None
    with open(out, "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(COLUMNS)
        try:
            while t_end is None or time.time() < t_end:
                raw = ser.readline().decode("ascii", errors="replace")
                if not raw:
                    continue
                f = parse_line(raw)
                if f:
                    wr.writerow([f"{time.time():.3f}"] + f); good += 1
                    if good % 60 == 0:
                        fh.flush(); print(f"{good} lines, last: {raw.strip()}")
                elif raw.strip():
                    if raw.startswith("R,"):
                        bad += 1
                    else:
                        print(raw.strip())      # S, K, ERR, # lines
        except KeyboardInterrupt:
            pass
    print(f"saved {good} lines to {out} ({bad} damaged lines dropped)")


if __name__ == "__main__":
    main()
