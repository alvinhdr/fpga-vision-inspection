# PROTOCOL — UART text protocol between the ARM program and the PC

Serial port: 115200 baud, 8N1, no flow control (COM16 or COM17 on this laptop, check Device Manager).
Everything is plain ASCII, one message per line, lines end with `\r\n`. Lines that start with `#` are comments
(banner, help): the PC ignores them. Numbers use a decimal point and a fixed number of decimals (the ARM has no
float printf, so `fmt_fixed()` in `sw/inspect/main.c` writes them).

## ARM → PC

**Result line** (one per video frame that had a result set, about 60 per second, about 70 bytes each = about 4.2 kB/s of
the 11.5 kB/s the port can carry):

```
R,<frame>,<status>,<A_px>,<cx>,<cy>,<L_px>,<W_px>,<angle_deg>,<L_mm>,<W_mm>,<verdict>
R,1234,MEASURED,325,640.2,350.1,72.98,10.45,-87.9,10.00,1.43,PASS
```

| Field | Meaning |
|---|---|
| `frame` | result set counter (`FRAME_CNT`), a jump of more than 1 means skipped results |
| `status` | `NOPART` (area too small) · `EDGE` (part touches the window edge) · `NOISY` (box ratio too big) · `MEASURED` |
| `A_px` | object pixels after the filter |
| `cx, cy` | centre in frame coordinates (pixels, 1 decimal) |
| `L_px, W_px` | equivalent rectangle length and width (pixels, 2 decimals) |
| `angle_deg` | long axis angle, image y points down (1 decimal) |
| `L_mm, W_mm` | millimetres, `0.00` when not calibrated |
| `verdict` | `PASS` · `FAIL` · `NOCAL` (no calibration yet) · `NONE` (status is not MEASURED) |

**Status line** (answer to `s`): `S,id=0x1a570001,ctrl=0x7,thresh=120,win=400 240 480 360,k_mm_px=0.1370,L_nom=10.00,L_tol=1.00,frames=...,results=...,skipped=...,video=1`

**Calibration answer** (to `k`): `K,<mm_per_px>`. Errors: `ERR <text>`.

## PC → ARM (commands, one line each, ended by Enter)

| Command | Effect |
|---|---|
| `?` | help (a `#` line) |
| `s` | status line |
| `m 0` / `m 1` | result lines off / on |
| `t <0..255>` | threshold |
| `p 0\|1` | polarity: 1 = part brighter than T |
| `f 0\|1` | 3x3 majority filter off / on |
| `o 0\|1` | overlay (frame, box, cross, colour) on the TV |
| `b 0\|1` | binary view |
| `w x0 y0 W H` | inspection window (checked against 1280x720) |
| `n <mm> <tol>` | nominal length and tolerance in mm |
| `k <mm>` | calibrate: the part now in the window is `<mm>` long (needs a MEASURED frame) |
| `c <mm/px>` | set the calibration directly |
| `z` | reset the skipped / result counters |

## Not in the protocol yet (honest list)

No checksum and no start marker beyond the line start: a corrupted line is dropped by the PC parser if it does
not have exactly 12 fields or an unknown status. A checksum field can be added later without breaking old logs
(extra last field). The PC tool `py/uart_log.py` writes every valid `R` line to a CSV with a PC timestamp; the
replay mode of the operator apps reads that CSV.
