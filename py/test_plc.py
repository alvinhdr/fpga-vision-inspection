"""
test_plc.py - tests of the PLC link (no board needed):
  1. Modbus frames checked byte by byte against the protocol description;
  2. server + client roundtrip (registers, coils, error answers);
  3. interoperability: the INDEPENDENT library pymodbus reads our server;
  4. whole chain: recorded board results -> gateway -> Modbus -> simulated PLC; the PLC's own counters must equal the
     gateway's (22 parts, PASS 14, FAIL 8), every FAIL part must give one reject pulse, and the line stop must be raised
     exactly when 3 FAIL parts came in a row.
  .\.venv\Scripts\python.exe py\test_plc.py
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modbus_mini import ModbusClient, ModbusData, ModbusError, ModbusServer, handle_pdu  # noqa: E402
from plc_gateway import (C_LINE_STOP, C_REJECT, C_RESET, R_FAIL, R_LAST_VERDICT, R_PARTS, R_PASS, R_SYSTEM_OK,  # noqa: E402
                         VisionGateway)
from plc_sim import PlcLogic, run  # noqa: E402
from viewer import csv_source  # noqa: E402

fails = []


def check(name, cond, info=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {info}" if info and not cond else ""))
    if not cond:
        fails.append(name)


# 1. raw frames --------------------------------------------------------------------------------------------------
d = ModbusData()
d.set_reg(0, 0x1234)
d.set_reg(1, 0xABCD)
resp = handle_pdu(bytes([3, 0, 0, 0, 2]), d)
check("read holding registers 0..1 -> 03 04 12 34 AB CD", resp == bytes([3, 4, 0x12, 0x34, 0xAB, 0xCD]), resp.hex())
check("read beyond the table -> exception 02", handle_pdu(bytes([3, 0, 199, 0, 5]), d) == bytes([0x83, 2]))
check("read 0 registers -> exception 03", handle_pdu(bytes([3, 0, 0, 0, 0]), d) == bytes([0x83, 3]))
check("unknown function 0x2B -> exception 01", handle_pdu(bytes([0x2B, 0]), d) == bytes([0xAB, 1]))
check("write coil 5 ON echoes the request", handle_pdu(bytes([5, 0, 5, 0xFF, 0]), d) == bytes([5, 0, 5, 0xFF, 0]) and d.get_coil(5))
check("write coil with value 0x1234 -> exception 03", handle_pdu(bytes([5, 0, 5, 0x12, 0x34]), d) == bytes([0x85, 3]))
d.set_coil(0, True); d.set_coil(2, True)
check("read coils 0..2 -> bits 101 = 0x05", handle_pdu(bytes([1, 0, 0, 0, 3]), d) == bytes([1, 1, 0x05]))

# 2. roundtrip over TCP -------------------------------------------------------------------------------------------
srv = ModbusServer("127.0.0.1", 0).start()
cl = ModbusClient("127.0.0.1", srv.port)
srv.data.set_reg(7, 4242)
check("client reads register 7 = 4242", cl.read_holding(7, 1) == [4242])
cl.write_register(20, 777)
check("client writes register 20 = 777", srv.data.get_reg(20) == 777)
cl.write_coil(3, True)
check("client writes coil 3, reads it back", cl.read_coils(3, 1) == [True])
try:
    cl.read_holding(199, 5)
    check("client sees the exception for a bad address", False)
except ModbusError as e:
    check("client sees the exception for a bad address", "exception 2" in str(e), str(e))
cl.close()

# 3. interoperability with pymodbus (independent implementation) -----------------------------------------------------
try:
    from pymodbus.client import ModbusTcpClient
    srv.data.set_reg(0, 11); srv.data.set_reg(1, 22); srv.data.set_reg(9, 99); srv.data.set_coil(1, True)
    pc = ModbusTcpClient("127.0.0.1", port=srv.port)
    check("pymodbus connects", pc.connect())
    try:
        rr = pc.read_holding_registers(0, count=10, device_id=1)
    except TypeError:
        rr = pc.read_holding_registers(0, count=10, slave=1)
    check("pymodbus reads our registers", (not rr.isError()) and rr.registers[0] == 11 and rr.registers[1] == 22 and rr.registers[9] == 99,
          str(rr))
    try:
        rc = pc.read_coils(0, count=3, device_id=1)
    except TypeError:
        rc = pc.read_coils(0, count=3, slave=1)
    check("pymodbus reads our coils", (not rc.isError()) and rc.bits[1] is True, str(rc))
    try:
        pc.write_register(30, 1234, device_id=1)
    except TypeError:
        pc.write_register(30, 1234, slave=1)
    check("pymodbus writes a register on our server", srv.data.get_reg(30) == 1234)
    pc.close()
except ImportError:
    print("SKIP  pymodbus not installed")
srv.stop()

# 3b. the PLC logic alone (pure function) ------------------------------------------------------------------------------
def regs_with(p_, f_, last):
    r = [0] * 10
    r[R_SYSTEM_OK] = 1; r[R_PASS] = p_; r[R_FAIL] = f_; r[R_LAST_VERDICT] = last
    return r


lg = PlcLogic()
seq = [(1, 0, 1), (1, 1, 2), (2, 1, 1), (2, 2, 2), (2, 3, 2), (3, 3, 1)]     # P F P F F P: never 3 FAIL in a row
stops = []
for pp, ff, last in seq:
    stops.append(lg.scan(regs_with(pp, ff, last), 100)[1])
check("isolated FAILs never raise the line stop", not any(stops), str(stops))
check("PLC counted 3 PASS and 3 FAIL in that sequence", (lg.pass_seen, lg.fail_seen) == (3, 3))
lg = PlcLogic()
out = [lg.scan(regs_with(0, ff, 2), 100) for ff in (1, 2, 3)]
check("3 FAIL in a row raise the line stop on the third", [o[1] for o in out] == [False, False, True])
check("the line stop stays latched, the acknowledge clears it",
      lg.scan(regs_with(0, 3, 2), 100)[1] and not lg.scan(regs_with(0, 3, 2), 100, ack=True)[1])
lg = PlcLogic()
r1 = lg.scan(regs_with(0, 1, 2), 100)[0]                                  # FAIL: reject on for 500 ms
rs = [lg.scan(regs_with(0, 1, 2), 100)[0] for _ in range(6)]
check("reject pulse lasts about 500 ms (5 scans of 100 ms)", r1 and rs[:4] == [True] * 4 and rs[5] is False, str(rs))

# 4. whole chain -----------------------------------------------------------------------------------------------------
csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "runs", "20261020_final.csv")
srv = ModbusServer("127.0.0.1", 0).start()
gw = VisionGateway(srv)
cl = ModbusClient("127.0.0.1", srv.port)
import threading  # noqa: E402
th = threading.Thread(target=lambda: gw.run_source(csv_source(csv_path, 0), speed=40.0), daemon=True)
th.start()
logic = PlcLogic()
state = {"stop_seen": False}


def done():
    return gw.finished.is_set()


logic = run(cl, 5, done, logic)
for _ in range(10):                                      # a few more scans after the last part
    regs = cl.read_holding(0, 10)
    logic.scan(regs, 5)
    time.sleep(0.005)
th.join(5)
parts = gw.tr.parts
verdicts = [p["verdict"] for p in parts]
run_len = best = 0
for v in verdicts:
    run_len = run_len + 1 if v == "FAIL" else 0
    best = max(best, run_len)
print(f"gateway: {len(parts)} parts, PASS {gw.tr.n_pass}, FAIL {gw.tr.n_fail}; longest FAIL run {best}")
check("gateway counted 22 parts, PASS 14, FAIL 8 (same as Python viewer and C# app)",
      (len(parts), gw.tr.n_pass, gw.tr.n_fail) == (22, 14, 8))
check("registers hold the final counts", (srv.data.get_reg(R_PARTS), srv.data.get_reg(R_PASS), srv.data.get_reg(R_FAIL)) == (22, 14, 8))
check("PLC's own counters equal the gateway's", (logic.pass_seen, logic.fail_seen) == (14, 8), f"{logic.pass_seen}/{logic.fail_seen}")
check("one reject pulse per FAIL part", logic.pulses_started == 8, str(logic.pulses_started))
check("line stop raised exactly when 3 FAIL parts came in a row", logic.line_stop == (best >= 3), f"best run {best}, stop {logic.line_stop}")
check("gateway sees the PLC's line-stop coil", srv.data.get_coil(C_LINE_STOP) == logic.line_stop)
check("SYSTEM_OK is 1 right after the results", srv.data.get_reg(R_SYSTEM_OK) == 1)
time.sleep(3.6)                                          # the replay is over: the watchdog must notice the silence
check("SYSTEM_OK falls to 0 when no results arrive for 2 s", srv.data.get_reg(R_SYSTEM_OK) == 0)
lg2 = PlcLogic(); lg2.scan([0] * 10, 100)
check("PLC logic raises COMM_FAULT when SYSTEM_OK = 0", lg2.comm_fault)
# reset coil clears the counters
cl.write_coil(C_RESET, True)
gw.check_reset()
check("RESET coil clears the counters and clears itself", srv.data.get_reg(R_PARTS) == 0 and not srv.data.get_coil(C_RESET))
cl.close(); gw.stop(); srv.stop()

print("\nALL PLC TESTS PASSED" if not fails else f"\n{len(fails)} TEST(S) FAILED: {fails}")
sys.exit(1 if fails else 0)
