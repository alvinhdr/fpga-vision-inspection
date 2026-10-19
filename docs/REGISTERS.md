# REGISTERS — AXI4-Lite register map (implemented in `rtl/axil_insp.sv`, M4)

Base address `0x43C0_0000` (64 KB window, set in `scripts/build_hw.tcl`). All registers are 32 bits, word
aligned, accessed by the ARM (`sw/common/insp_regs.h` has the same list). Clock domain of the registers: `clk_acc`
(100 MHz). Anything that the pixel pipeline uses crosses to `clk_pix` (74.25 MHz) as described in the last section.
Change it only together with `insp_regs.h`, this file and `tb/tb_axil_insp.sv`.

## Control and settings (RW)

| Offset | Name | Bits | Reset | Meaning |
|---|---|---|---|---|
| 0x000 | `ID` | RO | `0x1A570001` | project tag + register map version |
| 0x004 | `CTRL` | RW | `0x00000007` | [0] `POL` 1 = object brighter than T, 0 = darker · [1] `FILT_EN` 3x3 majority filter · [2] `OVERLAY_EN` draw window frame, bounding box, centre cross, PASS/FAIL colour · [3] `BINARY_VIEW` show the filtered object mask inside the window (what the FPGA sees) |
| 0x008 | `THRESH` | RW | 120 | [7:0] threshold T |
| 0x00C | `WIN_POS` | RW | y0 = 240, x0 = 400 | [10:0] x0 · [26:16] y0 |
| 0x010 | `WIN_SIZE` | RW | H = 360, W = 480 | [10:0] W · [26:16] H. The ARM must write legal values (`x0 + W <= 1280`, `y0 + H <= 720`) |

Settings are copied to `clk_pix` together (one request/acknowledge bus crossing, as in the previous project) and
take effect at the start of the next frame, never in the middle of one.

## Status and result set (RO)

| Offset | Name | Meaning |
|---|---|---|
| 0x014 | `STATUS` | [0] `READY_BANK` (which result bank is the newest complete one) · [1] `VIDEO_LOCKED` (HDMI input locked) |
| 0x018 | `FRAME_CNT` | number of complete result sets since reset (counts one per frame that had a window) |
| 0x01C | `PIX_FRAMES` | all video frames seen since reset (60 per second); for the frame-rate test |

**Result set** (the newest complete bank; the hardware reads/writes the other bank for the next frame):

| Offset | Name | Meaning |
|---|---|---|
| 0x040 | `R_A` | [19:0] A, object pixels |
| 0x044 | `R_SX` | [29:0] ΣU |
| 0x048 | `R_SY` | [28:0] ΣV |
| 0x04C | `R_SXX_LO` | [31:0] ΣU², low word |
| 0x050 | `R_SXX_HI` | [6:0] ΣU², bits 38..32 |
| 0x054 | `R_SYY_LO` | ΣV², low word |
| 0x058 | `R_SYY_HI` | [5:0] ΣV², bits 37..32 |
| 0x05C | `R_SXY_LO` | ΣU·V, low word |
| 0x060 | `R_SXY_HI` | [5:0] ΣU·V, bits 37..32 |
| 0x064 | `R_BBOX_U` | [10:0] UMIN · [26:16] UMAX |
| 0x068 | `R_BBOX_V` | [10:0] VMIN · [26:16] VMAX |
| 0x06C | `R_FRAME_ID` | same value as `FRAME_CNT` (the AXI-side bank pointer and the counter change in the same clock) |

**How the ARM reads it safely** (no locking is needed): a bank stays unchanged for one whole video frame (16.7 ms)
after it becomes ready; reading 14 words takes a few microseconds.
1. `id0 = FRAME_CNT`. 2. Read all result words. 3. `id1 = FRAME_CNT` and `R_FRAME_ID`.
4. If `R_FRAME_ID != id0`, or `id1 - id0 >= 2` (the bank may have been overwritten), read again.
A new result set appears when `FRAME_CNT` changes.

## Overlay (RW, written by the ARM after it has done the maths)

| Offset | Name | Meaning |
|---|---|---|
| 0x080 | `OVL_VERDICT` | [2:0] 0 = nothing drawn, 1 = `PASS` (green frame), 2 = `FAIL` (red frame), 3 = `NOISY/EDGE` (yellow frame) |
| 0x084 | `OVL_CENTRE` | [10:0] cx · [26:16] cy, in FRAME coordinates (x0 and y0 already added); the hardware draws a cross there |

The bounding box is drawn by the hardware itself from the result set (UMIN/UMAX/VMIN/VMAX + window origin), so
it needs no ARM help. The text ("24.1 mm", letters PASS/FAIL) comes later in the Standard tier:
`0x1000 + 4*i` = character RAM (reserved, not in M4).

## Reserved

`0x2000 + 4*i` histogram bins (RO, 256 x 20 bit, Standard tier, two banks like the result set). Everything else is
reserved: reads return 0, writes are ignored.

## Clock domain crossing (details go to `docs/CDC.md` in M4)

- `CTRL`, `THRESH`, `WIN_*`, `OVL_*`: `clk_acc` → `clk_pix`, one multi-bit req/ack crossing (`cdc_bus_sync`).
- Results: `clk_pix` → `clk_acc`. The result banks are written by the pixel side and read by the AXI side; the bank
  bit and the frame counter go through 2-flop synchronizers (`READY_BANK`) and a pulse synchronizer, and the data
  words are only read while their bank is not being written (the rule above), so no data word is ever sampled
  while it changes.
