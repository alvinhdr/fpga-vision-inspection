"""
plc_gateway.py - "vision gateway": publishes the inspection results as Modbus TCP registers, the way a vision system
talks to a PLC. Project: Real-Time FPGA Vision Inspection Station

Input: the board over the serial port (--port COM11), or a recorded CSV (--csv ..., no board needed; --speed 1 = real time).
Output: Modbus TCP server (default 127.0.0.1:5020, unit 1). Register map (also in docs/PLC.md):

  Holding registers (read by the PLC, 16 bit unsigned):
    0 HEARTBEAT         +1 every second while the gateway runs
    1 SYSTEM_OK         1 = results arrived within the last 2 s, 0 = board / replay silent
    2 PART_PRESENT      1 = a part is in the inspection window now
    3 LAST_VERDICT      verdict of the last finished part: 0 none, 1 PASS, 2 FAIL
    4 PARTS_TOTAL       finished parts
    5 PASS_COUNT        finished parts that passed
    6 FAIL_COUNT        finished parts that failed
    7 LAST_LENGTH_X100  median length of the last finished part, mm x 100
    8 YIELD_X10         PASS_COUNT / PARTS_TOTAL in percent x 10
    9 LIVE_LENGTH_X100  length of the part in the window now, mm x 100 (0 if none)
  Coils (written by the PLC, 1 bit):
    0 REJECT            reject actuator output (set by the PLC for a pulse)
    1 LINE_STOP         line-stop alarm (set by the PLC)
    2 RESET             PLC / HMI asks to reset the counters; the gateway clears the coil afterwards

A part is counted by the same rules as py/viewer.py and the C# app (Tracker).
  .\\.venv\\Scripts\\python.exe py\\plc_gateway.py --csv data\\runs\\20261020_final.csv --speed 20
"""
import argparse
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modbus_mini import ModbusServer  # noqa: E402
from viewer import Tracker, csv_source, serial_source  # noqa: E402

(R_HEARTBEAT, R_SYSTEM_OK, R_PART_PRESENT, R_LAST_VERDICT, R_PARTS, R_PASS, R_FAIL, R_LAST_LEN, R_YIELD, R_LIVE_LEN) = range(10)
C_REJECT, C_LINE_STOP, C_RESET = 0, 1, 2


class VisionGateway:
    def __init__(self, server, nom=None, tol=None):
        self.server = server
        self.d = server.data
        self.tr = Tracker(nom, tol)
        self.last_feed = 0.0
        self.finished = threading.Event()          # the source ended (replay finished)
        self._stop = threading.Event()
        self.log = []                              # (time, text) of PLC writes seen by the gateway
        threading.Thread(target=self._housekeeping, daemon=True).start()

    def _housekeeping(self):
        """Heartbeat every second, SYSTEM_OK watchdog, RESET coil."""
        n = 0
        while not self._stop.is_set():
            self.d.set_reg(R_HEARTBEAT, n := (n + 1) & 0xFFFF)
            self.d.set_reg(R_SYSTEM_OK, 1 if time.time() - self.last_feed < 2.0 else 0)
            self._stop.wait(1.0)

    def check_reset(self):
        if self.d.get_coil(C_RESET):
            self.tr = Tracker(self.tr.nom, self.tr.tol)
            for r in (R_LAST_VERDICT, R_PARTS, R_PASS, R_FAIL, R_LAST_LEN, R_YIELD):
                self.d.set_reg(r, 0)
            self.d.set_coil(C_RESET, False)
            self.log.append((time.time(), "counters reset by PLC"))

    def feed(self, f):
        """One measurement (dict of the R-line fields)."""
        self.last_feed = time.time()
        self.d.set_reg(R_SYSTEM_OK, 1)
        n_before = len(self.tr.parts)
        self.tr.feed(f)
        measured = f["status"] == "MEASURED"
        self.d.set_reg(R_PART_PRESENT, 1 if f["status"] != "NOPART" else 0)
        self.d.set_reg(R_LIVE_LEN, round(float(f["L_mm"]) * 100) if measured else 0)
        if len(self.tr.parts) > n_before:
            self._publish(self.tr.parts[-1])
        self.check_reset()

    def _publish(self, p):
        d = self.d
        d.set_reg(R_LAST_VERDICT, 1 if p["verdict"] == "PASS" else 2)
        d.set_reg(R_PARTS, len(self.tr.parts))
        d.set_reg(R_PASS, self.tr.n_pass)
        d.set_reg(R_FAIL, self.tr.n_fail)
        d.set_reg(R_LAST_LEN, round(p["L_mm"] * 100))
        d.set_reg(R_YIELD, round(self.tr.yield_pct * 10))

    def finish(self):
        self.tr.finish()
        if self.tr.parts and self.d.get_reg(R_PARTS) != len(self.tr.parts):
            self._publish(self.tr.parts[-1])
        self.finished.set()

    def run_source(self, source, speed=0.0):
        """Feed all measurements of a source; speed = times real time (0 = as fast as possible)."""
        due = 0.0
        for f, _ in source:
            self.feed(f)
            if speed and speed > 0:
                due += 1 / 60 / speed
                if due >= 0.004:                   # sleep in chunks: short sleeps are inaccurate
                    time.sleep(due)
                    due = 0.0
        self.finish()

    def stop(self):
        self._stop.set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--port")
    ap.add_argument("--listen", type=int, default=5020)
    args = ap.parse_args()
    if not (args.csv or args.port):
        sys.exit("give --csv <file> or --port COM11")
    srv = ModbusServer("127.0.0.1", args.listen,
                       on_write=lambda kind, a, v: print(f"PLC wrote {kind} {a} = {v}", flush=True)).start()
    gw = VisionGateway(srv)
    print(f"Modbus TCP server on 127.0.0.1:{srv.port}, unit 1. Press Ctrl+C to stop.", flush=True)
    src = csv_source(args.csv, 0) if args.csv else serial_source(args.port, 115200, None)
    try:
        gw.run_source(src, args.speed if args.csv else 0.0)
        print("source finished; server stays up for 30 s", flush=True)
        time.sleep(30)
    except KeyboardInterrupt:
        pass
    gw.stop()
    srv.stop()


if __name__ == "__main__":
    main()
