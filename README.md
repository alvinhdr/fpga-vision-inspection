# Real-Time FPGA Vision Inspection Station

Work in progress. A camera looks at a small part on a table. The live video goes over HDMI into a Zybo Z7-10 board. Hand-written SystemVerilog measures the part on every frame at 60 FPS, without a frame buffer. The result (size, position, angle, PASS/FAIL) is drawn on the video and sent to a PC.

See `PLAN.md` for the milestones and `notes/PROGRESS.md` for the current state.
