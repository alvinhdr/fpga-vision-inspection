// =============================================================================
// File   : tb_meas_core.sv
// Project: Real-Time FPGA Vision Inspection Station
// Purpose: Plays recorded 1280x720 frames (raw RGB file from scripts/sim_meas.py) through
//          pix_pos_counter + meas_core with video timing, and writes one line per result set.
//          scripts/sim_meas.py compares every line with py/golden.py (bit-exact).
//
// Plusargs (no "=": Windows .bat files split at it): +IN_<frames.bin> +OUT_<results.txt> +FRAMES_<n>
//           +X0_<n> +Y0_ +W_ +H_ +T_ +POL_ +FILT_   (settings, same meaning as py/golden.py Settings)
//           +HBL_<clocks>  horizontal blanking (default 12; real 720p: 370)
//           +ALT_1 with +X0B_ +Y0B_ +WB_ +HB_ +TB_ +POLB_ +FILTB_ : odd frames use these settings B; the
//           change is applied in the clock where pix_pos_counter raises sof (tests the latch-at-sof path)
// Output line: A SX SY SXX SYY SXY UMIN UMAX VMIN VMAX  (decimal)
// =============================================================================
`timescale 1ns/1ps
`default_nettype none

module tb_meas_core;
    import video_pkg::*;
    import insp_pkg::*;

    localparam int FW = 1280, FH = 720;
    localparam int VBL = 4300;            // > pix_pos_counter VBLANK_MIN (4096) and > flush (W+1)

    logic clk = 1'b0;
    always #5 clk = ~clk;

    video_t        vid_in = '0, vid_pos;
    logic [CW-1:0] x, y;
    logic          sof;
    meas_cfg_t     cfg;
    meas_res_t     res;
    logic          done, f_valid, f;
    logic [CW-1:0] f_u, f_v;

    pix_pos_counter u_pos (.clk_pix(clk), .i_vid(vid_in), .o_vid(vid_pos), .o_x(x), .o_y(y), .o_sof(sof));

    meas_core u_dut (
        .clk_pix(clk), .i_vid(vid_pos), .i_x(x), .i_y(y), .i_sof(sof),
        .i_cfg(cfg), .o_cfg(), .o_f_valid(f_valid), .o_f(f), .o_f_u(f_u), .o_f_v(f_v),
        .o_res(res), .o_done(done)
    );

    string in_file, out_file;
    int    n_frames, hbl, fd_in, fd_out, n_done = 0;
    int    x0, y0, w, h, t, pol, filt, alt;
    int    x0b, y0b, wb, hb, tb_, polb, filtb;
    meas_cfg_t cfg_a, cfg_b;
    logic [7:0] line_buf [0:FW*3-1];

    always @(posedge clk) begin
        if (done) begin
            $fdisplay(fd_out, "%0d %0d %0d %0d %0d %0d %0d %0d %0d %0d", res.a, res.sx, res.sy, res.sxx,
                      res.syy, res.sxy, res.umin, res.umax, res.vmin, res.vmax);
            n_done++;
        end
    end

    task automatic blank(input int n);
        vid_in.de <= 1'b0;
        repeat (n) @(posedge clk);
    endtask

    initial begin
        if (!$value$plusargs("IN_%s", in_file))     $fatal(1, "need +IN");
        if (!$value$plusargs("OUT_%s", out_file))   $fatal(1, "need +OUT");
        if (!$value$plusargs("FRAMES_%d", n_frames)) n_frames = 1;
        if (!$value$plusargs("HBL_%d", hbl))        hbl = 12;
        if (!$value$plusargs("X0_%d", x0))   x0 = 400;
        if (!$value$plusargs("Y0_%d", y0))   y0 = 240;
        if (!$value$plusargs("W_%d", w))     w = 480;
        if (!$value$plusargs("H_%d", h))     h = 360;
        if (!$value$plusargs("T_%d", t))     t = 120;
        if (!$value$plusargs("POL_%d", pol)) pol = 1;
        if (!$value$plusargs("FILT_%d", filt)) filt = 1;
        cfg_a = '{x0: x0[10:0], y0: y0[10:0], w: w[10:0], h: h[10:0], thresh: t[7:0], pol: pol[0], filt_en: filt[0]};
        if (!$value$plusargs("ALT_%d", alt)) alt = 0;
        if (!$value$plusargs("X0B_%d", x0b))   x0b = x0;
        if (!$value$plusargs("Y0B_%d", y0b))   y0b = y0;
        if (!$value$plusargs("WB_%d", wb))     wb = w;
        if (!$value$plusargs("HB_%d", hb))     hb = h;
        if (!$value$plusargs("TB_%d", tb_))    tb_ = t;
        if (!$value$plusargs("POLB_%d", polb)) polb = pol;
        if (!$value$plusargs("FILTB_%d", filtb)) filtb = filt;
        cfg_b = '{x0: x0b[10:0], y0: y0b[10:0], w: wb[10:0], h: hb[10:0], thresh: tb_[7:0], pol: polb[0], filt_en: filtb[0]};
        cfg   = cfg_a;

        fd_in  = $fopen(in_file, "rb");
        fd_out = $fopen(out_file, "w");
        if (fd_in == 0 || fd_out == 0) $fatal(1, "cannot open files");

        blank(VBL);
        for (int fr = 0; fr < n_frames; fr++) begin
            for (int yy = 0; yy < FH; yy++) begin
                if ($fread(line_buf, fd_in) != FW * 3) $fatal(1, "input file too short (frame %0d)", fr);
                for (int xx = 0; xx < FW; xx++) begin
                    // settings for this frame: applied when the 2nd pixel enters, i.e. in the clock where
                    // pix_pos_counter shows sof for the 1st pixel (frame 0 keeps the start value A)
                    if (alt && yy == 0 && xx == 1) cfg <= (fr % 2) ? cfg_b : cfg_a;
                    vid_in.de   <= 1'b1;
                    vid_in.data <= pack_rgb(line_buf[3*xx], line_buf[3*xx+1], line_buf[3*xx+2]);
                    @(posedge clk);
                end
                blank(hbl);
            end
            blank(VBL);
        end
        blank(10);
        $fclose(fd_out);
        if (n_done == n_frames) $display("TEST DONE: %0d frames, %0d result sets", n_frames, n_done);
        else                    $display("TEST FAILED: %0d frames but %0d result sets", n_frames, n_done);
        $finish;
    end
endmodule

`default_nettype wire
