"""
viewer.py - operator view for the inspection station: live numbers, big PASS/FAIL tile, yield, trend chart
with the tolerance band, CSV log. Works LIVE from the serial port or as REPLAY of a recorded CSV (no board needed).
Project: Real-Time FPGA Vision Inspection Station

  .\\.venv\\Scripts\\python.exe py\\viewer.py --replay data\\runs\\20261020_final.csv --speed 20
  .\\.venv\\Scripts\\python.exe py\\viewer.py --port COM11 --log data\\runs\\live.csv --nom 11.3 --tol 1.6
  .\\.venv\\Scripts\\python.exe py\\viewer.py --replay data\\runs\\20261020_final.csv --selftest   (no window)

A "part" is counted when a part stays in the window and then leaves (NOPART for 0.25 s) or the recording breaks
(frame number jumps). Its verdict is the majority of its PASS / FAIL lines; parts with fewer than 20 decided lines
are ignored. Yield = PASS parts / counted parts. Input lines: docs/PROTOCOL.md (R lines) or the CSV written by
py/uart_log.py and py/evidence.py (extra columns are ignored).
"""
import argparse
import collections
import csv
import os
import queue
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uart_log import COLUMNS, parse_line, strip_stale_prefix  # noqa: E402

FIELDS = COLUMNS[1:]          # frame, status, A_px, cx, cy, L_px, W_px, angle_deg, L_mm, W_mm, verdict


class Tracker:
    """All viewer logic without any window: part counting, yield, trend buffer."""

    GAP_FRAMES = 15           # NOPART frames in a row that end a part
    MAX_JUMP = 100            # a frame-number jump larger than this = new recording (smaller jumps are lost UART lines)
    MIN_DECIDED = 20

    def __init__(self, nom=None, tol=None, trend_len=400):
        self.nom, self.tol = nom, tol
        self.trend = collections.deque(maxlen=trend_len)      # (frame, L_mm, verdict)
        self.parts = []                                       # finished parts: dict(verdict, n, L_median)
        self.cur = collections.Counter()
        self.cur_L = []
        self.nopart_run = 0
        self.last_frame = None
        self.last = None
        self.lines = 0

    def feed(self, f):
        """f = dict with the R-line fields (strings or numbers)."""
        frame = int(f["frame"])
        self.lines += 1
        if self.last_frame is not None and not 0 <= frame - self.last_frame <= self.MAX_JUMP:
            self._close()                                     # recording break or restart
        self.last_frame = frame
        self.last = f
        st, vd = f["status"], f["verdict"]
        if st == "NOPART":
            self.nopart_run += 1
            if self.nopart_run >= self.GAP_FRAMES:
                self._close()
        else:
            self.nopart_run = 0
        if vd in ("PASS", "FAIL"):
            self.cur[vd] += 1
            self.cur_L.append(float(f["L_mm"]))
        if st == "MEASURED":
            self.trend.append((frame, float(f["L_mm"]), vd))

    def _close(self):
        n = self.cur["PASS"] + self.cur["FAIL"]
        if n >= self.MIN_DECIDED:
            v = "PASS" if self.cur["PASS"] >= self.cur["FAIL"] else "FAIL"
            Ls = sorted(self.cur_L)
            self.parts.append({"verdict": v, "n": n, "L_mm": Ls[len(Ls) // 2]})
        self.cur = collections.Counter()
        self.cur_L = []

    def finish(self):
        self._close()

    @property
    def n_pass(self):
        return sum(p["verdict"] == "PASS" for p in self.parts)

    @property
    def n_fail(self):
        return sum(p["verdict"] == "FAIL" for p in self.parts)

    @property
    def yield_pct(self):
        n = len(self.parts)
        return 100.0 * self.n_pass / n if n else float("nan")


def csv_source(path, speed):
    """Yield field dicts from a CSV, paced by the recorded PC time (or 60 lines/s), speed x faster."""
    rows = list(csv.DictReader(open(path)))
    if rows and "group" in rows[0]:                      # evidence file: remove the stale line prefix of each recording
        rows, _ = strip_stale_prefix(rows)
    t_prev = None
    for r in rows:
        f = {k: r.get(k) for k in FIELDS}
        if any(v is None for v in f.values()):
            continue
        yield f, r
        t = float(r["pc_time"]) if r.get("pc_time") else None
        if speed and speed > 0:
            dt = (t - t_prev) if (t is not None and t_prev is not None and 0 <= t - t_prev < 1) else 1 / 60
            time.sleep(max(0.0, dt / speed))
        t_prev = t


def serial_source(port, baud, log_path):
    import serial
    ser = serial.Serial(port, baud, timeout=0.2)
    fh = open(log_path, "w", newline="") if log_path else None
    wr = csv.writer(fh) if fh else None
    if wr:
        wr.writerow(COLUMNS)
    while True:
        p = parse_line(ser.readline().decode("ascii", "replace"))
        if p:
            if wr:
                wr.writerow([f"{time.time():.3f}"] + p)
            yield dict(zip(FIELDS, p)), None


def selftest(path):
    tr = Tracker()
    truth = []
    cls_of_part = []
    cur = collections.Counter()
    for f, raw in csv_source(path, 0):
        tr.feed(f)
    tr.finish()
    print(f"{tr.lines} lines -> {len(tr.parts)} parts counted: PASS {tr.n_pass}, FAIL {tr.n_fail}, yield {tr.yield_pct:.1f} %")
    # compare with the class column of the evidence file (if present): each recording of 3 s / 10 s is one part
    rows = list(csv.DictReader(open(path)))
    rows, _ = strip_stale_prefix(rows)
    if rows and "class" in rows[0]:
        by = collections.OrderedDict()
        for r in rows:
            if r.get("group") in ("acc", "repeat"):
                by.setdefault((r["group"], r["part"], r["placement"]), []).append(r)
        good = sum(1 for k, v in by.items() if v[0]["class"] == "good")
        print(f"evidence file has {len(by)} recordings ({good} good, {len(by) - good} bad); counted {len(tr.parts)} parts")
    return tr


# ----------------------------------------------------------------------------------------------- GUI
def run_gui(args):
    import tkinter as tk

    tr = Tracker(args.nom, args.tol)
    q = queue.Queue(maxsize=5000)
    src = csv_source(args.replay, args.speed) if args.replay else serial_source(args.port, 115200, args.log)

    def reader():
        for f, _ in src:
            q.put(f)
        q.put(None)

    threading.Thread(target=reader, daemon=True).start()

    root = tk.Tk()
    root.title("Inspection station" + (" - replay" if args.replay else " - live"))
    root.geometry("980x600")
    root.configure(bg="#111")
    tile = tk.Label(root, text="--", font=("Arial", 64, "bold"), fg="white", bg="#444", width=7)
    tile.place(x=20, y=20, width=300, height=170)
    info = tk.Label(root, text="", font=("Consolas", 14), fg="#ddd", bg="#111", justify="left", anchor="nw")
    info.place(x=340, y=20, width=620, height=170)
    stats = tk.Label(root, text="", font=("Arial", 18, "bold"), fg="white", bg="#111", anchor="w")
    stats.place(x=20, y=200, width=940, height=36)
    cv = tk.Canvas(root, bg="#1b1b1b", highlightthickness=0)
    cv.place(x=20, y=245, width=940, height=335)
    colors = {"PASS": "#1faa3c", "FAIL": "#d62d2d", "NOCAL": "#aa8a1f", "NONE": "#555"}
    state = {"done": False}

    def draw_trend():
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        pts = list(tr.trend)
        if not pts:
            return
        lo = min(p[1] for p in pts); hi = max(p[1] for p in pts)
        if args.nom is not None:
            lo = min(lo, args.nom - args.tol - 1); hi = max(hi, args.nom + args.tol + 1)
        span = max(hi - lo, 1e-6)
        y = lambda v: h - 20 - (v - lo) / span * (h - 40)
        if args.nom is not None:
            cv.create_rectangle(0, y(args.nom + args.tol), w, y(args.nom - args.tol), fill="#17301b", outline="")
            for v in (args.nom - args.tol, args.nom, args.nom + args.tol):
                cv.create_line(0, y(v), w, y(v), fill="#3c6e45", dash=(4, 3))
        n = len(pts)
        for i in range(1, n):
            cv.create_line((i - 1) * w / n, y(pts[i - 1][1]), i * w / n, y(pts[i][1]), fill=colors.get(pts[i][2], "#888"))
        cv.create_text(6, 6, anchor="nw", fill="#aaa", text=f"length (mm), last {n} measured frames; band = nominal +- tolerance")
        cv.create_text(w - 6, h - 6, anchor="se", fill="#aaa", text=f"{lo:.1f} .. {hi:.1f} mm")

    def tick():
        for _ in range(400):
            try:
                f = q.get_nowait()
            except queue.Empty:
                break
            if f is None:
                state["done"] = True
                tr.finish()
                break
            tr.feed(f)
        if tr.last:
            f = tr.last
            v = f["verdict"] if f["status"] == "MEASURED" else (f["status"] if f["status"] != "MEASURED" else "NONE")
            tile.config(text=v if v in ("PASS", "FAIL") else v[:6], bg=colors.get(v, "#555"))
            info.config(text=(f"frame {f['frame']}   status {f['status']}\n"
                              f"length {float(f['L_mm']):7.2f} mm   ({float(f['L_px']):.1f} px)\n"
                              f"width  {float(f['W_mm']):7.2f} mm   ({float(f['W_px']):.1f} px)\n"
                              f"angle  {float(f['angle_deg']):6.1f} deg   area {f['A_px']} px\n"
                              f"centre {f['cx']}, {f['cy']}"))
            y = tr.yield_pct
            stats.config(text=f"parts {len(tr.parts)}   PASS {tr.n_pass}   FAIL {tr.n_fail}   yield "
                              f"{'--' if y != y else f'{y:.1f} %'}" + ("   (replay finished)" if state["done"] else ""))
            draw_trend()
        root.after(60, tick)

    tick()
    root.mainloop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay")
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed factor (0 = as fast as possible)")
    ap.add_argument("--port")
    ap.add_argument("--log", default=None, help="CSV file for live mode")
    ap.add_argument("--nom", type=float, default=None, help="nominal length for the tolerance band")
    ap.add_argument("--tol", type=float, default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest(args.replay)
        return
    if not (args.replay or args.port):
        sys.exit("give --replay <csv> or --port COM11")
    run_gui(args)


if __name__ == "__main__":
    main()
