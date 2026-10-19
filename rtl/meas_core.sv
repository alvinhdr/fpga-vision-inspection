// =============================================================================
// File   : meas_core.sv
// Project: Real-Time FPGA Vision Inspection Station
// Purpose: Streaming per-frame measurement (docs/MEASUREMENT.md sections 1-5), clk_pix domain,
//          no frame buffer. Bit-exact twin of py/golden.py.
//
//   video (x, y from pix_pos_counter)
//     S0  gray -> object bit (threshold, polarity), only inside the window; window coords u, v
//     E   registered window "event"  {valid, u, v, obj}
//     G   event generator: real events, + one PAD column (u = W, obj 0) after each window row,
//         + one FLUSH row (v = H, u = 0..W, obj 0) after the last row. Pad and flush give the
//         filter its zero border, so the edge pixels of the window are finished without
//         waiting for more video. (Needs >= 1 clock without a window pixel after each window
//         row: always true, the horizontal blanking is 370 clocks.)
//     F1  2-row line buffer read + 3x3 window of columns
//     F2  filtered pixel f for the CENTRE (u-1, v-1)  (majority >= 5 of 9, or the raw bit)
//     A1-A3  products u*u, v*v, u*v (DSP48) and the 40-bit accumulators + bounding box
//   o_done: 1-clock pulse when the result set of the frame is complete (after the flush row).
//
//   Settings are latched at the start of the frame (i_sof), so they never change inside a frame.
//   Accumulators are cleared at i_sof; the result set stays valid until the next i_sof.
//   LAT_F = 4: an event that enters S0 at clock t leaves F2 at clock t+4 (for the video overlay).
// =============================================================================
`default_nettype none

module meas_core
    import video_pkg::*;
    import insp_pkg::*;
#(
    parameter int LB_DEPTH = 2048      // line buffer depth: >= max window width + 1 (pad column)
) (
    input  wire              clk_pix,

    // Video with position (outputs of pix_pos_counter, aligned)
    input  video_t           i_vid,
    input  wire  [CW-1:0]    i_x,
    input  wire  [CW-1:0]    i_y,
    input  wire              i_sof,

    input  meas_cfg_t        i_cfg,       // settings (clk_pix domain), latched at i_sof
    output meas_cfg_t        o_cfg,       // settings of the current frame

    // Filtered pixel stream (for the binary view), F2 stage
    output logic             o_f_valid,
    output logic             o_f,
    output logic [CW-1:0]    o_f_u,       // centre coordinates (window)
    output logic [CW-1:0]    o_f_v,

    // Results
    output meas_res_t        o_res,
    output logic             o_done
);

    localparam int LAT_F = 4;   // documented for top.sv / testbenches

    // ---- S0: settings, window test, gray, object bit (combinational) ------------------------
    meas_cfg_t cfg_q = CFG_DEFAULT;
    meas_cfg_t cfg;                                    // settings that apply to this pixel
    assign cfg   = i_sof ? i_cfg : cfg_q;
    assign o_cfg = cfg_q;

    logic [7:0]    gray;
    logic          in_win, obj;
    logic [CW:0]   x_end, y_end;                       // one extra bit: x0 + w can be 1280+
    logic [CW-1:0] u, v;

    rgb2gray u_gray (.i_data(i_vid.data), .o_gray(gray));

    always_comb begin
        x_end  = {1'b0, cfg.x0} + {1'b0, cfg.w};
        y_end  = {1'b0, cfg.y0} + {1'b0, cfg.h};
        in_win = i_vid.de && (i_x >= cfg.x0) && ({1'b0, i_x} < x_end) &&
                             (i_y >= cfg.y0) && ({1'b0, i_y} < y_end);
        u      = i_x - cfg.x0;
        v      = i_y - cfg.y0;
        obj    = cfg.pol ? (gray > cfg.thresh) : (gray < cfg.thresh);
    end

    always_ff @(posedge clk_pix) if (i_sof) cfg_q <= i_cfg;

    // ---- E: registered window event --------------------------------------------------------
    logic          e_valid = 1'b0, e_obj, e_lastcol, e_lastrow;
    logic [CW-1:0] e_u, e_v;

    always_ff @(posedge clk_pix) begin
        e_valid   <= in_win;
        e_u       <= u;
        e_v       <= v;
        e_obj     <= obj;
        e_lastcol <= (u == cfg.w - 1'b1);
        e_lastrow <= (v == cfg.h - 1'b1);
    end

    // ---- G: event generator (real events, pad column, flush row) -------------------------------
    logic          g_valid = 1'b0, g_obj = 1'b0, g_last = 1'b0;
    logic [CW-1:0] g_u = '0, g_v = '0;
    logic          pad_pend_q = 1'b0, pad_lastrow_q = 1'b0, flush_q = 1'b0;
    logic [CW-1:0] pad_v_q = '0, flush_u_q = '0;

    always_ff @(posedge clk_pix) begin
        g_valid <= 1'b0;
        g_last  <= 1'b0;
        if (e_valid) begin
            g_valid <= 1'b1;
            g_u     <= e_u;
            g_v     <= e_v;
            g_obj   <= e_obj;
            if (e_lastcol) begin
                pad_pend_q    <= 1'b1;
                pad_v_q       <= e_v;
                pad_lastrow_q <= e_lastrow;
            end
        end else if (pad_pend_q) begin
            g_valid    <= 1'b1;
            g_u        <= cfg_q.w;                       // the column right of the window
            g_v        <= pad_v_q;
            g_obj      <= 1'b0;
            pad_pend_q <= 1'b0;
            if (pad_lastrow_q) begin
                flush_q   <= 1'b1;
                flush_u_q <= '0;
            end
        end else if (flush_q) begin
            g_valid <= 1'b1;
            g_u     <= flush_u_q;
            g_v     <= cfg_q.h;                          // the row below the window
            g_obj   <= 1'b0;
            if (flush_u_q == cfg_q.w) begin              // last flush event (its pad column)
                flush_q <= 1'b0;
                g_last  <= 1'b1;
            end else begin
                flush_u_q <= flush_u_q + 1'b1;
            end
        end
    end

    // ---- F1: line buffer (2 bits per column: rows v-1 and v-2) + 3x3 column window ------------
    // Read with the G address, data arrives in F1; write in F1 for the next row. A column is read
    // again only one full row later (>= W+1 events), so there is no read/write collision.
    (* ram_style = "block" *) logic [1:0] lb [0:LB_DEPTH-1];
    logic [1:0]    lb_rd_q;
    logic          f1_valid = 1'b0, f1_obj = 1'b0, f1_last = 1'b0, f1_pad = 1'b0;
    logic [CW-1:0] f1_u = '0, f1_v = '0;

    always_ff @(posedge clk_pix) begin
        lb_rd_q  <= lb[g_u];
        f1_valid <= g_valid;
        f1_u     <= g_u;
        f1_v     <= g_v;
        f1_obj   <= g_obj;
        f1_last  <= g_last;
        f1_pad   <= (g_u == cfg_q.w);
    end

    logic       r1, r2;          // object bits of rows v-1 and v-2 in this column (0 above the window)
    logic [2:0] col;             // {row v-2, row v-1, row v} of column u
    always_comb begin
        r1  = (f1_v == '0)                    ? 1'b0 : lb_rd_q[0];
        r2  = (f1_v == '0 || f1_v == 11'd1)   ? 1'b0 : lb_rd_q[1];
        col = f1_pad ? 3'b000 : {r2, r1, f1_obj};
    end

    always_ff @(posedge clk_pix) begin
        if (f1_valid && !f1_pad) lb[f1_u] <= {r1, f1_obj};   // for the next row: [0] row v, [1] row v-1
    end

    logic [2:0] p1_q = '0, p2_q = '0;   // columns u-1 and u-2 (zero at the row start: the pad
                                        // column of the previous row is all zeros)
    logic [3:0] cnt;
    always_comb cnt = 4'(p2_q[0]) + 4'(p2_q[1]) + 4'(p2_q[2]) + 4'(p1_q[0]) + 4'(p1_q[1]) +
                      4'(p1_q[2]) + 4'(col[0])  + 4'(col[1])  + 4'(col[2]);

    // ---- F2: filtered centre pixel (u-1, v-1) ------------------------------------------------
    logic          f2_valid = 1'b0, f2_f = 1'b0, f2_last = 1'b0;
    logic [CW-1:0] f2_u = '0, f2_v = '0;

    always_ff @(posedge clk_pix) begin
        f2_valid <= f1_valid && (f1_u != '0) && (f1_v != '0);
        f2_u     <= f1_u - 1'b1;
        f2_v     <= f1_v - 1'b1;
        f2_f     <= cfg_q.filt_en ? (cnt >= 4'd5) : p1_q[1];     // p1_q[1] = centre (u-1, v-1)
        f2_last  <= f1_last;
        if (f1_valid) begin
            p2_q <= p1_q;
            p1_q <= col;
        end
    end

    assign o_f_valid = f2_valid;
    assign o_f       = f2_f;
    assign o_f_u     = f2_u;
    assign o_f_v     = f2_v;

    // ---- A1-A3: products and accumulators ----------------------------------------------------
    logic          a1_hit = 1'b0, a1_last = 1'b0;
    logic [CW-1:0] a1_u = '0, a1_v = '0;
    logic          a2_hit = 1'b0, a2_last = 1'b0;
    logic [CW-1:0] a2_u = '0, a2_v = '0;
    logic [21:0]   a2_uu = '0, a2_vv = '0, a2_uv = '0;

    always_ff @(posedge clk_pix) begin
        a1_hit  <= f2_valid && f2_f;
        a1_last <= f2_last;
        a1_u    <= f2_u;
        a1_v    <= f2_v;
        a2_hit  <= a1_hit;
        a2_last <= a1_last;
        a2_u    <= a1_u;
        a2_v    <= a1_v;
        a2_uu   <= a1_u * a1_u;
        a2_vv   <= a1_v * a1_v;
        a2_uv   <= a1_u * a1_v;
    end

    meas_res_t acc_q = '0;
    logic      done_q = 1'b0;

    always_ff @(posedge clk_pix) begin
        done_q <= a2_last;
        if (i_sof) begin
            acc_q      <= '0;
            acc_q.umin <= '1;
            acc_q.vmin <= '1;
        end else if (a2_hit) begin
            acc_q.a   <= acc_q.a   + 1'b1;
            acc_q.sx  <= acc_q.sx  + a2_u;
            acc_q.sy  <= acc_q.sy  + a2_v;
            acc_q.sxx <= acc_q.sxx + a2_uu;
            acc_q.syy <= acc_q.syy + a2_vv;
            acc_q.sxy <= acc_q.sxy + a2_uv;
            if (a2_u < acc_q.umin) acc_q.umin <= a2_u;
            if (a2_u > acc_q.umax) acc_q.umax <= a2_u;
            if (a2_v < acc_q.vmin) acc_q.vmin <= a2_v;
            if (a2_v > acc_q.vmax) acc_q.vmax <= a2_v;
        end
    end

    assign o_res  = acc_q;
    assign o_done = done_q;

endmodule

`default_nettype wire
