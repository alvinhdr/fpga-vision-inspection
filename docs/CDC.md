# CDC — every clock domain crossing in the design

Clocks: `clk_pix` 74.25 MHz (recovered from the laptop's HDMI, by `dvi2rgb`), `clk_acc` 100 MHz (ARM `FCLK_CLK0`,
AXI-Lite registers), `clk_sys` 125 MHz and `clk_ref` 200 MHz (board oscillator, PLL). They come from three different
sources, so they are **asynchronous**: `constraints/zybo_z7_10_impl.xdc` declares them as asynchronous clock groups,
so the timing tool does not check paths between them. Every such path must therefore be made safe **by design**,
as listed here.

| # | Signal(s) | From → to | Method | Where |
|---|---|---|---|---|
| 1 | All settings: window, threshold, polarity, filter, overlay on, binary view, verdict, centre (81 bits) | clk_acc → clk_pix | One **request/acknowledge** bus crossing: the source holds the value constant, a toggle is synchronized with 2 flops, the destination copies the stable value. All bits change together. Inside the pixel side, the measurement settings are latched again at the start of a frame, so a change never happens in the middle of a frame. | `cdc_bus_sync` in `top.sv`; latch in `meas_core.sv` |
| 2 | Result sets (2 banks, about 230 bits each) | clk_pix → clk_acc | **Quasi-static data + synchronized event.** The pixel side writes bank `wr_bank`, then flips `wr_bank` and `done_toggle`. The AXI side synchronizes `done_toggle` with 2 flops; its `bank_q` is simply `~done_toggle` (the pixel side flips `wr_bank` and `done_toggle` together, both from 0), and `FRAME_CNT` counts the toggle's changes **in the same clock**. Because the pointer has no state of its own, it stays correct even if the AXI side is reset while video runs (found in the RTL review, test added). `bank_q` always points to the bank finished last; that bank is not written again until two result sets later (at least one more video frame, 16.7 ms), so its bits are stable when the AXI side reads them. The ARM reads `FRAME_CNT` before and after the result words and retries if it changed (`insp_read_result()` in `sw/common/insp_regs.h`). | `insp_pipeline.sv` (banks), `axil_insp.sv` (pointer, counter) |
| 3 | Start of every video frame (`sof_toggle`) | clk_pix → clk_acc | Toggle + 2 flops + edge detect → `PIX_FRAMES` counter (frame-rate test). Events 16.7 ms apart, far slower than 3 destination clocks. | `insp_pipeline.sv`, `axil_insp.sv` |
| 4 | HDMI locked (`pix_locked`) | clk_pix → clk_acc and clk_sys | 2 flops (single bit, slow level). | `axil_insp.sv` (STATUS bit 1), `top.sv` (LED) |
| 5 | Switches sw[0], sw[1] | asynchronous → clk_pix | 2 flops (single bits). | `top.sv` |
| 6 | Inside Digilent `dvi2rgb` / `rgb2dvi` | their own clocks | Digilent's own synchronizers (the CDC report lists warnings inside these IPs; same as the previous project). | third-party IP |

## Why not a synchronizer on every bit of the result?
Two flops per bit do not keep a multi-bit value together: the bits can arrive one clock apart, and a reader could
see half old, half new. A 40-bit sum would then be wrong by a huge amount. Method 2 never reads bits while they
change, so no per-bit synchronizer is needed, and the AXI read is a simple multiplexer.

## Verification
- `tb/tb_cdc.sv` (reused): bus and pulse synchronizers with two unrelated clocks.
- `tb/tb_axil_insp.sv`: two clocks (100 / 74.25 MHz); after each `done` toggle the newest bank is read with the
  correct `FRAME_CNT`; a bank keeps its value while the pixel side writes the other one; a result set finished while
  the AXI side is in reset is still the one read afterwards. Mutation checks: starting the bank pointer on the wrong
  bank, and the first (counted) pointer design, both make the test fail.
- `tb/tb_meas_core.sv` + `scripts/sim_meas.py`: the pixel-side results, bit-exact against `py/golden.py`.

## Known limits (honest list)
- `WIN_POS` and `WIN_SIZE` are two separate AXI writes, so they can reach the pixel side in two transfers and one
  frame may be measured with a mixed window (or produce no result if the mix is outside the frame). The ARM program
  ignores the next two result sets after a window change (`sw/inspect/main.c`).
- The paths of methods 1 and 2 have no `set_max_delay` constraint (the clock groups make them false paths). This is
  safe because the data is stable for thousands of clocks before it is used, but a stricter design would add
  `set_max_delay -datapath_only` on them. Same choice as the previous project.
- If the HDMI input stops in the middle of a frame, no result set is produced for that frame (no `done`), so
  `FRAME_CNT` simply stops; the ARM sees no new results. The last result stays on the screen.
