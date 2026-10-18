# LEARNING — glossary and interview Q&A

Every new concept goes here (plain English). Add one interview question with a short answer per module.

## Glossary
- **Pass-through**: the video goes into the FPGA and out again unchanged (or with small drawings on top). It is the base that every later feature is built on.
- **Frame buffer**: memory that stores a whole picture. We do not use one. Pixels are processed while they stream past, so the delay is only a few clock cycles (nanoseconds), not a whole frame (16.7 ms).
- **Reuse**: copying proven modules from an older project (HDMI input/output, clock-crossing blocks). Normal in industry, and it lets us spend board time on new work. Each reused file keeps its header and says where it came from.
- **EDID**: a small data block that tells the laptop which video modes the screen accepts. Ours lists only 1280x720@60 so Windows does not choose 1080p (too fast for this chip).
- **AXI-Lite stub**: a placeholder bus slave that answers every read with an ID, so the ARM cannot hang while the real registers do not exist yet.

## Interview Q&A
- **M0 - Why reuse the HDMI blocks from your last project?** Because they were already verified on the board with timing met. Reusing them means any new problem must come from the new code, which makes debugging much faster.

## M1 - capture and lighting
- **Threshold**: a gray level T that splits "part" from "background". Here the part is brighter than the black mat, so a pixel is "part" if gray > T.
- **Exposure lock**: the phone camera normally changes its brightness by itself (auto exposure). That moves the gray levels, so a fixed threshold stops working. We lock it, or we compute the threshold per frame (Otsu).
- **Otsu threshold**: a method that looks at the histogram (how many pixels have each gray level) and picks the T that best separates two groups (dark mat, bright part). Our own frames show why it is needed: the same mat was gray 18 in one session and gray 50 in another.
- **Good / bad parts**: a PASS/FAIL system must be tested with parts it should accept and parts it should reject, otherwise "always PASS" would look perfect.
- **Interview Q&A (M1)**: *Why a black background with bright metal parts?* High contrast makes the threshold easy and robust: the part is far above the background even with soft edges. *Why record data before building the hardware?* The same real frames are used to design the maths, to test the RTL bit-exactly, and to measure accuracy later, even after the board is returned.
