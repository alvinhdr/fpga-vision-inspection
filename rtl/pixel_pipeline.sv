// =============================================================================
// File   : pixel_pipeline.sv
// Project: Real-Time FPGA Vision Inspection Station
// Purpose: M0 pass-through pixel path (clk_pix domain, no frame buffer):
//          position counter -> optional gray view -> window frame overlay.
//          The measurement core (threshold, moments, bbox) is added in M4.
//          Adapted from fpga-edge-ai-video (CNN, ROI capture and AI overlays removed).
//
//   LATENCY = 3 pixel clocks (pos counter 1, gray 1, overlay 1).
// =============================================================================
`default_nettype none

module pixel_pipeline
    import video_pkg::*;
#(
    parameter int WIN_SIZE = 240    // placeholder square frame; real window is rectangular (M4)
) (
    input  wire              clk_pix,
    input  video_t           i_vid,
    output video_t           o_vid,

    input  wire              i_gray_en,     // 1 = whole picture in grayscale
    input  wire              i_overlay_en,  // 1 = draw the window frame
    input  wire  [POS_W-1:0] i_win_x0,
    input  wire  [POS_W-1:0] i_win_y0
);

    localparam int LATENCY = 3;   // documented for testbenches

    // ---- Stage 1: pixel position ----------------------------------------
    video_t           s1_vid;
    logic [POS_W-1:0] s1_x, s1_y;

    pix_pos_counter u_pos (
        .clk_pix (clk_pix),
        .i_vid   (i_vid),
        .o_vid   (s1_vid),
        .o_x     (s1_x),
        .o_y     (s1_y),
        .o_sof   ()
    );

    // ---- Stage 2: optional grayscale view ---------------------------------
    video_t           s2_vid;
    logic [POS_W-1:0] s2_x, s2_y;
    logic [7:0]       s1_gray;

    rgb2gray u_gray (
        .i_data (s1_vid.data),
        .o_gray (s1_gray)
    );

    always_ff @(posedge clk_pix) begin
        s2_vid <= s1_vid;
        s2_x   <= s1_x;
        s2_y   <= s1_y;
        if (i_gray_en) s2_vid.data <= pack_rgb(s1_gray, s1_gray, s1_gray);
    end

    // ---- Stage 3: window frame ----------------------------------------------
    roi_overlay #(.ROI_SIZE(WIN_SIZE)) u_win (
        .clk_pix  (clk_pix),
        .i_vid    (s2_vid),
        .i_x      (s2_x),
        .i_y      (s2_y),
        .i_roi_x0 (i_win_x0),
        .i_roi_y0 (i_win_y0),
        .i_show   (i_overlay_en),
        .o_vid    (o_vid),
        .o_x      (),
        .o_y      ()
    );

endmodule

`default_nettype wire
