# PLC link: how the inspection station would talk to a PLC

In a real line the vision system does not stand alone: it tells a PLC "PASS" or "FAIL", and the PLC pushes the bad part out and stops
the line when too many fail. This project has **no PLC hardware**, so the link is built and tested in software:

```
board --UART--> py/plc_gateway.py  --Modbus TCP-->  py/plc_sim.py (simulated PLC scan loop)
(or a recorded CSV)   "vision gateway"  port 5020, unit 1     reads registers, writes coils
```

* `py/modbus_mini.py`: Modbus TCP server and client written from the protocol description (MBAP header + PDU). Function codes 1, 3, 4, 5, 6, 16
  and the exception answers. **Checked against the independent library `pymodbus`** (reads registers and coils, writes a register).
* `py/plc_gateway.py`: publishes the results (same part-counting rules as `py/viewer.py` and the C# app).
* `py/plc_sim.py`: a **software simulation** of PLC logic: read inputs, run the program, write outputs, every scan. It is **not** a real PLC and
  **not** OpenPLC.
* `py/test_plc.py`: 30 checks: byte-exact frames, loopback, pymodbus interoperability, the PLC logic alone (including cases where the line stop
  must NOT trigger), and the whole chain on the real recorded board results. A planted bug (stop after 2 FAILs) is caught by 2 tests.

## Register map (unit 1, TCP port 5020, 16-bit unsigned)

| Holding register | Name | Meaning |
|---|---|---|
| 0 | HEARTBEAT | +1 every second while the gateway runs |
| 1 | SYSTEM_OK | 1 = results arrived in the last 2 s, 0 = board / replay silent |
| 2 | PART_PRESENT | 1 = a part is in the inspection window now |
| 3 | LAST_VERDICT | verdict of the last finished part: 0 none, 1 PASS, 2 FAIL |
| 4 | PARTS_TOTAL | finished parts |
| 5 | PASS_COUNT | finished parts that passed |
| 6 | FAIL_COUNT | finished parts that failed |
| 7 | LAST_LENGTH_X100 | median length of the last finished part, mm x 100 |
| 8 | YIELD_X10 | percent x 10 |
| 9 | LIVE_LENGTH_X100 | length of the part in the window now, mm x 100 (0 = none) |

| Coil (written by the PLC) | Name | Meaning |
|---|---|---|
| 0 | REJECT | reject actuator output (pulse of 500 ms per FAIL part) |
| 1 | LINE_STOP | line-stop alarm after 3 FAIL parts in a row, latched until acknowledged |
| 2 | RESET | ask the gateway to reset the counters (the gateway clears the coil) |

## The PLC program (the same logic as IEC 61131-3 Structured Text, for a real PLC)

This text is the logic of `PlcLogic.scan()`; it was **not** run on a real PLC or in OpenPLC.

```
(* inputs: PassCount, FailCount, LastVerdict, SystemOk (read by Modbus TCP); outputs: Reject, LineStop *)
VAR LastPass, LastFail : UINT; ConsecFail : INT; PulseTimer : TON; END_VAR

NewPass := PassCount - LastPass;   NewFail := FailCount - LastFail;
LastPass := PassCount;             LastFail := FailCount;

IF NewFail > 0 THEN
    ConsecFail := ConsecFail + NewFail;
    PulseTimer(IN := FALSE);  PulseTimer(IN := TRUE, PT := T#500ms);      (* restart the reject pulse *)
END_IF;
IF NewPass > 0 AND LastVerdict = 1 THEN ConsecFail := 0; END_IF;
IF ConsecFail >= 3 THEN LineStop := TRUE; END_IF;
IF Acknowledge THEN LineStop := FALSE; ConsecFail := 0; END_IF;

Reject    := PulseTimer.IN AND NOT PulseTimer.Q;                         (* on while the 500 ms timer runs *)
CommFault := (SystemOk = 0);
```

## Run it
```
.\.venv\Scripts\python.exe py\test_plc.py                                                   (tests, no board needed)
.\.venv\Scripts\python.exe py\plc_gateway.py --csv data\runs\20261020_final.csv --speed 20  (terminal 1)
.\.venv\Scripts\python.exe py\plc_sim.py --scan-ms 100 --seconds 40                          (terminal 2)
```
With the live board: `py\plc_gateway.py --port COM11` (close PuTTY and any other program on that port first).

## Honest limits
- Real PLCs usually run a Modbus **client** that reads the vision server, or the vision system writes into the PLC; both use the same register
  ideas, and this server-side design is the usual one for a camera. Real PLC vendors add features not tested here (several unit ids, timeouts,
  byte and word order, 32-bit values; here every value is 16 bit).
- No real PLC, no OpenPLC, no 24 V signals: the reject and line-stop outputs are Modbus coils. On the Zybo a single output pin could carry the
  FAIL signal (a few lines of RTL), but that was not built and the board is returned.
- The parts are counted on the PC (gateway), not on the ARM.
- Live operation with the board was not tested (the board was returned); the tests use the recorded board results.
