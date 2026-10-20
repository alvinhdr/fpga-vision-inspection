# B2 — first live measurement (board session 2)

Goal: the real hardware measures the bolts live; numbers on the UART and the overlay on the monitor; record the
evidence. **Board last day: 21 Oct.** Plan about 2 hours. The assistant runs the commands; you do the physical steps.

## Ready before the session
- [x] Bitstream `build/inspect.bit` from commit `c45c811`: timing met (WNS +1.060 ns, WHS +0.033 ns), 2,197 LUT.
- [x] ARM program `build/sw/inspect.elf` (-O2). Unit tests pass (tb_cdc, tb_axil_insp incl. reset-during-traffic).
- [ ] Full bit-exact run `scripts/sim_meas.py` on the final RTL (running; result goes into PROGRESS.md).
- [x] Tools: `py/still_test.py` (bit-exact check ON the board with still frames), `py/uart_log.py` (CSV log),
      `py/grab_hdmi.py` (frames), PuTTY session `zybo` for typing commands.

## Physical setup (you)
1. Boot jumper on **JTAG**, power jumper USB. USB cable + both HDMI cables as in B1. Board on.
2. Laptop: **Extend** mode, board screen 1280x720 @ 60 Hz. **Night light OFF** and HDR off (they change the colours).
3. Phone + IP Webcam as before, lamp unchanged, mat cleaned with tape.

## Session order (about 2 h)
| # | What | Who | Time |
|---|---|---|---|
| 1 | Program: `xsdb scripts/program.tcl all inspect` (bitstream + ARM). Expect LEDs as in B1, the white window frame on the monitor, UART banner + `S,id=0x1a570001,...` | assistant | 5 min |
| 2 | **Still test**: `py/still_test.py COM16 --n 20` shows 20 recorded frames on the board screen; every board result must equal the golden model exactly. If A is off everywhere: laptop sends limited-range colours → NVIDIA Control Panel → Display → "Output dynamic range: Full" | the assistant (you watch) | 10 min |
| 3 | **s2 re-capture** (camera only): empty x5, ruler x2 (whole ruler with tick edge inside the picture), bolt_good_01..05 x5, bad_a..d x5 (`py/grab_hdmi.py --session s2`) | you + the assistant | 30 min |
| 4 | The assistant computes from s2: mm per pixel from the ruler, the threshold, the good bolt's nominal length | assistant | 10 min |
| 5 | Live: `t <T>`, `c <mm/px>`, `n <mm> <tol>`; binary view (`b 1`) to check what the FPGA sees; bolts PASS, bad parts FAIL on the monitor and in the result lines | both | 15 min |
| 6 | **Record evidence** (`py/uart_log.py COM16 --seconds 20 --out data/runs/...`): one good bolt still, 3 positions (repeatability); each good bolt 3 placements; each bad part 3 placements | you place, the assistant logs | 30 min |
| 7 | Frame rate: `s` now and after 60 s (`PIX_FRAMES` vs results, skipped) | assistant | 2 min |
| 8 | Photos of the monitor (PASS, FAIL, binary view) + a 20 s phone video | you | 10 min |
| 9 | Notes: hours used, results, problems → PROGRESS.md, commit | assistant | 5 min |

## If something goes wrong
- No second screen / LEDs off → re-program (step 1). `ps7_init` error right after power-on → run it again.
- `ERR wrong ID` → wrong bitstream loaded. No `R,` lines → `m 1`; check `S` line: `frames=` must grow (HDMI locked).
- Do not debug from zero on the board: write down what you see, take a photo, continue with the next step.
