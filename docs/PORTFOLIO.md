# PORTFOLIO — CV bullets, interview answers, LinkedIn draft

Only measured numbers are used (source: `docs/RESULTS.md`). Do not add claims that are not in that file.

## CV bullets (pick 3-4)
- Built a real-time machine-vision inspection station on a Zynq-7010 (Digilent Zybo Z7-10): hand-written SystemVerilog measures a part from live 720p60 camera video **without a frame buffer** (81 ns pipeline delay, **60.003 fps, 0 skipped results**), 12.5 % of the chip, timing met (WNS +1.06 ns).
- Verified the streaming hardware **bit-exactly** against an integer Python model on 285 real camera frames (at two thresholds) and edge cases in simulation (13 / 13 cases), against OpenCV (285 / 285 frames), and **on the board** (20 / 20 frames); a code review found and I fixed a real clock-domain-crossing bug.
- Measured the system on the real board: repeatability **0.06-0.07 mm** (std, still part), good bolts **15 / 15 placements PASS**, wrong parts **11 / 12 FAIL** (none wrongly passed); found and fixed three practical problems (camera auto-exposure, a mouse pointer counted as a part, flickering specks).
- Wrote bare-metal C for the ARM (moment-based centre / angle / length / width, calibration from a ruler, median filtering, PASS/FAIL), a text protocol over UART, and a Python operator view with replay of recorded logs. Tested a learned classifier on the measured features (honest result: no better than a tolerance rule).

## Why did you make this project? (30-second answer)
"I wanted one complete system from the sensor to the PC: hardware in the FPGA, firmware on the ARM and software on the PC, on a real signal. I chose measuring a part because the answer can be checked with a ruler, so I could prove with numbers that it works, and also find out where it does not: shiny parts change their measured length with the angle, and my reference ruler limits the accuracy. The FPGA does the per-pixel work at 55 million pixels per second; the ARM only does about twenty operations per frame."

## Likely interview questions (short answers)
- **Why sums in the FPGA and the angle on the ARM?** Per-pixel work must be simple multiply-adds (DSP blocks). The angle needs atan2 and square roots, but only 60 times per second.
- **Why no frame buffer?** All measurements are running sums, so a pixel is used once while it streams past. The delay is 6 clocks (81 ns), not a whole frame (16.7 ms), and no DDR bandwidth is needed.
- **How do you pass a 230-bit result to the ARM clock safely?** Two banks. The video side writes one bank, then flips a toggle bit. The ARM side synchronizes only that bit (2 flip-flops), derives its bank pointer from it and reads the other bank, which cannot change for a whole frame. The ARM also checks a frame counter before and after the read. (A first version of the pointer could be one frame stale after a reset: found in review, fixed, test added.)
- **How did you verify the hardware?** The same real frames go through the RTL in simulation and through an integer Python model; ten values per frame must be equal bit for bit. Edge cases: 1x1 window, full frame, settings that change exactly at frame start, 1 clock of blanking, synthetic frames at the maximum accumulator values. Then the same check on the board with recorded frames. OpenCV is an independent cross-check of the model.
- **What is your accuracy?** Repeatability is 0.06-0.07 mm for a still part. Absolute accuracy is limited by a ruler (+-1 mm) and the calibration (+-2 %); I did not have a caliper, so I do not claim accuracy against a caliper. Shiny long parts vary by 5-7 mm with the angle.
- **What would you improve?** Diffuse light (to remove glare), a caliper-measured reference set, a blind test set, connected-component labelling for several parts, and the SD-card boot test.
- **Did AI help?** On this data a learned model was not better than a tolerance rule; it needs no hand-set tolerance, which is its only advantage here. (docs/AI.md)

## LinkedIn draft
I built a real-time vision inspection station on an FPGA board.

A phone camera looks at a small metal part. The video goes through HDMI into a Zynq FPGA, where hand-written SystemVerilog measures the part while the pixels stream past: no frame buffer, 81 ns delay, 60 frames per second with no skipped result. An ARM program turns the sums into centre, angle, length and width and decides PASS or FAIL; the answer is drawn on the live picture and sent to a PC.

What I am most proud of is the checking: the hardware matches an integer Python model bit for bit on real camera frames, in simulation and on the board; the model matches OpenCV; a code review found a real clock-crossing bug that I fixed. On the board, a still part repeats to 0.06 mm, good bolts passed in 15 of 15 placements and wrong parts failed in 11 of 12.

I also wrote down what does not work well: shiny parts change length with the angle, my only reference was a ruler, and a learned classifier was not better than a simple tolerance rule.

Code, results with methods and limits: github.com/alvinhdr/fpga-vision-inspection (private until the final review, then public)
#FPGA #SystemVerilog #MachineVision #EmbeddedSystems
