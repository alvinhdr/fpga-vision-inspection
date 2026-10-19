// =============================================================================
// File   : insp_pipeline.sv
// Project: Real-Time FPGA Vision Inspection Station
// Purpose: Everything in the pixel clock domain (clk_pix, 74.25 MHz), no frame buffer:
//
//   i_vid -> pix_pos_counter -> [delay LAT_F] -> insp_overlay -> o_vid       (video path, 6 clocks)
//                   |
//                   +-> meas_core (threshold, 3x3 filter, accumulators) -> o_done
//                                   |
//                                   +-> result banks 0/1 (read by the AXI side, see docs/CDC.md)
//
// Result banks: when a frame's result set is complete, it is copied into bank[wr_bank], wr_bank
// flips, and o_done_toggle flips. The AXI side follows the toggle (its own bank pointer and frame
// counter change on the SAME synchronized edge), so it always reads the bank that was finished last,
// which stays unchanged for at least one more frame (16.7 ms). o_sof_toggle flips once per video frame.
// =============================================================================
`default_nettype none

module insp_pipeline
    import video_pkg::*;
    import insp_pkg::*;
(
    input  wire          clk_pix,
    input  video_t       i_vid,
    output video_t       o_vid,

    // settings, already in clk_pix (crossed in top.sv)
    input  meas_cfg_t    i_cfg,
    input  wire          i_ovl_en,
    input  wire          i_bin_view,
    input  wire [2:0]    i_verdict,
    input  wire [CW-1:0] i_cx,
    input  wire [CW-1:0] i_cy,

    // to the AXI side (clk_acc): read only, see header
    output meas_res_t    o_bank0,
    output meas_res_t    o_bank1,
    output logic         o_done_toggle,
    output logic         o_sof_toggle
);

    localparam int LAT_F = 4;       // meas_core: S0 -> F2

    // ---- position ----------------------------------------------------------------------
    video_t        s0_vid;
    logic [CW-1:0] s0_x, s0_y;
    logic          s0_sof;

    pix_pos_counter u_pos (
        .clk_pix(clk_pix), .i_vid(i_vid), .o_vid(s0_vid), .o_x(s0_x), .o_y(s0_y), .o_sof(s0_sof)
    );

    // ---- measurement ---------------------------------------------------------------------
    meas_cfg_t     cfg_frame;
    meas_res_t     res;
    logic          done, f_valid, f;

    meas_core u_meas (
        .clk_pix(clk_pix), .i_vid(s0_vid), .i_x(s0_x), .i_y(s0_y), .i_sof(s0_sof),
        .i_cfg(i_cfg), .o_cfg(cfg_frame),
        .o_f_valid(f_valid), .o_f(f), .o_f_u(), .o_f_v(),
        .o_res(res), .o_done(done)
    );

    // ---- result banks + last result for the overlay -----------------------------------------------
    meas_res_t     bank0_q = '0, bank1_q = '0;
    logic          wr_bank_q = 1'b0, done_tog_q = 1'b0, sof_tog_q = 1'b0;
    logic          box_valid_q = 1'b0;
    logic [CW-1:0] box_x0_q = '0, box_x1_q = '0, box_y0_q = '0, box_y1_q = '0;

    always_ff @(posedge clk_pix) begin
        if (s0_sof) sof_tog_q <= ~sof_tog_q;
        if (done) begin
            if (wr_bank_q) bank1_q <= res;
            else           bank0_q <= res;
            wr_bank_q   <= ~wr_bank_q;
            done_tog_q  <= ~done_tog_q;
            box_valid_q <= (res.a != '0);
            box_x0_q    <= cfg_frame.x0 + res.umin;
            box_x1_q    <= cfg_frame.x0 + res.umax;
            box_y0_q    <= cfg_frame.y0 + res.vmin;
            box_y1_q    <= cfg_frame.y0 + res.vmax;
        end
    end

    assign o_bank0       = bank0_q;
    assign o_bank1       = bank1_q;
    assign o_done_toggle = done_tog_q;
    assign o_sof_toggle  = sof_tog_q;

    // ---- video path: delay to line up with the filtered mask, then draw -----------------------------
    video_t        d_vid [LAT_F];
    logic [CW-1:0] d_x [LAT_F], d_y [LAT_F];

    always_ff @(posedge clk_pix) begin
        d_vid[0] <= s0_vid;
        d_x[0]   <= s0_x;
        d_y[0]   <= s0_y;
        for (int i = 1; i < LAT_F; i++) begin
            d_vid[i] <= d_vid[i-1];
            d_x[i]   <= d_x[i-1];
            d_y[i]   <= d_y[i-1];
        end
    end

    insp_overlay u_ovl (
        .clk_pix(clk_pix), .i_vid(d_vid[LAT_F-1]), .i_x(d_x[LAT_F-1]), .i_y(d_y[LAT_F-1]),
        .i_en(i_ovl_en), .i_bin_view(i_bin_view), .i_cfg(cfg_frame),
        .i_f_valid(f_valid), .i_f(f),
        .i_box_valid(box_valid_q), .i_box_x0(box_x0_q), .i_box_x1(box_x1_q),
        .i_box_y0(box_y0_q), .i_box_y1(box_y1_q),
        .i_verdict(i_verdict), .i_cx(i_cx), .i_cy(i_cy),
        .o_vid(o_vid)
    );

endmodule

`default_nettype wire
