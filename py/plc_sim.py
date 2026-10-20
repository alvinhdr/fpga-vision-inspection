"""
plc_sim.py - a simulated PLC: a scan loop that reads the gateway's Modbus registers and runs typical line logic.
Project: Real-Time FPGA Vision Inspection Station

This is a software simulation of PLC logic (a cyclic scan: read inputs, run the logic, write outputs), NOT a real PLC and
not OpenPLC. The same logic as IEC 61131-3 Structured Text is in docs/PLC.md.

Logic per scan:
  - count new good / bad parts from PASS_COUNT / FAIL_COUNT (differences since the last scan);
  - every new FAIL part starts a reject pulse of 500 ms on coil REJECT (several FAILs in one scan add pulses);
  - 3 FAIL parts in a row (the last verdict is FAIL each time) latch coil LINE_STOP until the operator acknowledges;
  - SYSTEM_OK = 0 (board or gateway silent) raises COMM_FAULT.

  .\\.venv\\Scripts\\python.exe py\\plc_sim.py --scan-ms 100 --seconds 60      (gateway must be running)
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modbus_mini import ModbusClient  # noqa: E402
from plc_gateway import (C_LINE_STOP, C_REJECT, R_FAIL, R_LAST_VERDICT, R_PASS, R_SYSTEM_OK)  # noqa: E402

PULSE_MS = 500
STOP_AFTER_FAILS = 3


class PlcLogic:
    """The program of the PLC: pure logic, no I/O, so it can be tested without a network."""

    def __init__(self):
        self.last_pass = self.last_fail = 0
        self.pass_seen = self.fail_seen = 0         # the PLC's own counters
        self.consecutive_fail = 0
        self.pulse_left_ms = 0
        self.pulses_started = 0
        self.line_stop = False
        self.comm_fault = False

    def scan(self, regs, dt_ms, ack=False):
        """regs: list of 10 holding registers. Returns the outputs (reject, line_stop)."""
        dp = (regs[R_PASS] - self.last_pass) & 0xFFFF
        df = (regs[R_FAIL] - self.last_fail) & 0xFFFF
        self.last_pass, self.last_fail = regs[R_PASS], regs[R_FAIL]
        self.pass_seen += dp
        self.fail_seen += df
        if df:
            self.pulses_started += df
            self.pulse_left_ms = PULSE_MS * 1 + max(0, df - 1) * PULSE_MS       # extra pulses queue up
            self.consecutive_fail += df
        if dp and regs[R_LAST_VERDICT] == 1:
            self.consecutive_fail = 0
        if self.consecutive_fail >= STOP_AFTER_FAILS:
            self.line_stop = True
        if ack:
            self.line_stop = False
            self.consecutive_fail = 0
        self.comm_fault = regs[R_SYSTEM_OK] == 0
        reject = self.pulse_left_ms > 0
        self.pulse_left_ms = max(0, self.pulse_left_ms - dt_ms)
        return reject, self.line_stop


def run(client, scan_ms, stop_when, logic=None, verbose=False):
    """Cyclic scan against a gateway until stop_when() is true. Returns the logic object (with its counters)."""
    logic = logic or PlcLogic()
    prev = (False, False)
    t_last = time.perf_counter()
    while not stop_when():
        t0 = time.perf_counter()
        regs = client.read_holding(0, 10)                      # 1. read inputs
        dt = int((t0 - t_last) * 1000) or scan_ms
        t_last = t0
        out = logic.scan(regs, dt)                             # 2. run the logic
        if out[0] != prev[0]:                                  # 3. write outputs (only when they change)
            client.write_coil(C_REJECT, out[0])
        if out[1] != prev[1]:
            client.write_coil(C_LINE_STOP, out[1])
        prev = out
        if verbose:
            print(f"PASS {logic.pass_seen}  FAIL {logic.fail_seen}  reject {int(out[0])}  line_stop {int(out[1])}"
                  f"{'  COMM FAULT' if logic.comm_fault else ''}", flush=True)
        time.sleep(max(0.0, scan_ms / 1000 - (time.perf_counter() - t0)))
    return logic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5020)
    ap.add_argument("--scan-ms", type=int, default=100)
    ap.add_argument("--seconds", type=float, default=60)
    args = ap.parse_args()
    cl = ModbusClient(args.host, args.port)
    t_end = time.time() + args.seconds
    lg = run(cl, args.scan_ms, lambda: time.time() > t_end, verbose=True)
    print(f"\nPLC totals: PASS {lg.pass_seen}, FAIL {lg.fail_seen}, reject pulses {lg.pulses_started}, "
          f"line stop {lg.line_stop}")


if __name__ == "__main__":
    main()
