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

## M2 - image moments and the golden model
- **Image moments**: sums over the part pixels. `A` = how many pixels (area). `SX/A, SY/A` = the average position (centre). The second moments (`SXX, SYY, SXY`) say how spread out the pixels are and in which direction: from them we get the angle and the length/width.
- **Why sums suit hardware**: a sum can be updated one pixel at a time (add, never look back), so it needs no frame buffer. Divisions and square roots are done once per frame by the ARM.
- **Equivalent rectangle**: a solid rectangle of n x m pixels has length = sqrt(12*l1 + 1) = n exactly. We use that formula for every part; for a bolt it is a very repeatable "equivalent length".
- **Golden model**: an exact integer Python version of what the hardware computes. The hardware must give the same bits. OpenCV is used as a second, independent opinion on the golden model.
- **Mutation test**: break the model on purpose (wrong filter rule, off-by-one) and check that the test fails. A test that cannot fail proves nothing.
- **Outliers**: one speck far away changes the second moments a lot (a distance squared). That is why we filter, check the box ratio (NOISY), and keep the mat clean.
- **Median and MAD**: the middle value and the typical distance from it. Unlike mean and std, a few bad frames hardly change them.
- **Interview Q&A (M2)**: *Why compute moments in the FPGA but the angle on the ARM?* The FPGA does 55 million pixels per second, so per-pixel work must be simple multiply-adds (DSP48 blocks). The angle needs atan2 and square roots, but only once per frame (60 per second), which is trivial for the ARM. *How do you know your accumulator cannot overflow?* The widths are computed for the worst case (every pixel of the full frame set) and the golden model asserts them on every frame.
