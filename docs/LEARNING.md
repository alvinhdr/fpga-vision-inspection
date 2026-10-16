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
