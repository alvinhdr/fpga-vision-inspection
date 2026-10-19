// =============================================================================
// File   : insp_overlay.sv
// Project: Real-Time FPGA Vision Inspection Station
// Purpose: Draw the inspection result on the live video (clk_pix, latency 1 clock, no frame buffer):
//            - window frame (3 px, OUTSIDE the window), colour = verdict:
//              none = white, PASS = green, FAIL = red, NOISY/EDGE = yellow
//            - bounding box of the last result (1 px, cyan), from the hardware result set itself
//            - centre cross at (cx, cy) written by the ARM (magenta, +-10 px), only if a verdict exists
//            - binary view: inside the window, the filtered object mask (white/black) instead of video.
//              The mask pixel of window position (u-1, v-1) is shown at video position (u, v): the
//              filter needs the next row and column first, so the view is shifted by 1 px right/down.
//          Priority: cross > box > frame > binary view > video.
// =============================================================================
`default_nettype none

module insp_overlay
    import video_pkg::*;
    import insp_pkg::*;
#(
    parameter int BORDER = 3,
    parameter int CROSS  = 10
) (
    input  wire            clk_pix,
    input  video_t         i_vid,
    input  wire [CW-1:0]   i_x,
    input  wire [CW-1:0]   i_y,

    input  wire            i_en,          // frame, box and cross on/off
    input  wire            i_bin_view,
    input  meas_cfg_t      i_cfg,         // current window
    input  wire            i_f_valid,     // filtered mask (aligned with i_vid, see header)
    input  wire            i_f,
    input  wire            i_box_valid,   // last result had object pixels
    input  wire [CW-1:0]   i_box_x0, i_box_x1, i_box_y0, i_box_y1,   // frame coordinates
    input  wire [2:0]      i_verdict,     // 0 none, 1 PASS, 2 FAIL, 3 other
    input  wire [CW-1:0]   i_cx, i_cy,

    output video_t         o_vid
);

    localparam logic [23:0] C_WHITE   = COLOR_WHITE;
    localparam logic [23:0] C_GREEN   = COLOR_GREEN;
    localparam logic [23:0] C_RED     = 24'hFF_00_00;    // {R, B, G}
    localparam logic [23:0] C_YELLOW  = 24'hFF_00_FF;    // R + G
    localparam logic [23:0] C_CYAN    = 24'h00_FF_FF;    // B + G
    localparam logic [23:0] C_MAGENTA = 24'hFF_FF_00;    // R + B

    // 14-bit signed arithmetic: coordinates +- border never wrap
    logic signed [13:0] x, y, wx0, wy0, wx1, wy1, cx, cy;
    logic in_outer, in_win, on_frame, on_box, on_cross;
    logic [23:0] frame_col;

    always_comb begin
        x   = 14'(i_x);
        y   = 14'(i_y);
        wx0 = 14'(i_cfg.x0);
        wy0 = 14'(i_cfg.y0);
        wx1 = 14'(i_cfg.x0) + 14'(i_cfg.w) - 14'sd1;     // last window column
        wy1 = 14'(i_cfg.y0) + 14'(i_cfg.h) - 14'sd1;
        cx  = 14'(i_cx);
        cy  = 14'(i_cy);

        in_win   = (x >= wx0) && (x <= wx1) && (y >= wy0) && (y <= wy1);
        in_outer = (x >= wx0 - BORDER) && (x <= wx1 + BORDER) && (y >= wy0 - BORDER) && (y <= wy1 + BORDER);
        on_frame = in_outer && !in_win;

        on_box = i_box_valid &&
                 (((x == 14'(i_box_x0) || x == 14'(i_box_x1)) && y >= 14'(i_box_y0) && y <= 14'(i_box_y1)) ||
                  ((y == 14'(i_box_y0) || y == 14'(i_box_y1)) && x >= 14'(i_box_x0) && x <= 14'(i_box_x1)));

        on_cross = (i_verdict != 3'd0) &&
                   ((y == cy && x >= cx - CROSS && x <= cx + CROSS) ||
                    (x == cx && y >= cy - CROSS && y <= cy + CROSS));

        unique case (i_verdict)
            3'd1:    frame_col = C_GREEN;
            3'd2:    frame_col = C_RED;
            3'd3:    frame_col = C_YELLOW;
            default: frame_col = C_WHITE;
        endcase
    end

    always_ff @(posedge clk_pix) begin
        o_vid <= i_vid;
        if (i_vid.de) begin
            if (i_en && on_cross)                       o_vid.data <= C_MAGENTA;
            else if (i_en && on_box)                    o_vid.data <= C_CYAN;
            else if (i_en && on_frame)                  o_vid.data <= frame_col;
            else if (i_bin_view && in_win && i_f_valid) o_vid.data <= i_f ? C_WHITE : COLOR_BLACK;
        end
    end

endmodule

`default_nettype wire
