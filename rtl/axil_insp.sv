// =============================================================================
// File   : axil_insp.sv
// Project: Real-Time FPGA Vision Inspection Station (AXI handshake pattern from fpga-edge-ai-video)
// Purpose: Hand-written AXI4-Lite slave, clk_acc (100 MHz). Register map: docs/REGISTERS.md
//          (same list in sw/common/insp_regs.h).
//
// Result banks (clk_pix registers, read here WITHOUT a synchronizer, on purpose):
//   i_done_toggle is synchronized (2 flops). bank_q = ~(synchronized toggle) and frame_cnt_q counts its
//   changes, in the SAME clock. bank_q always points at the bank the pixel side finished last; that bank is not
//   written again for at least one more video frame (16.7 ms), so its bits are stable whenever they
//   are read. The ARM reads FRAME_CNT before and after the result words and retries if it changed.
//   Full explanation: docs/CDC.md.
// =============================================================================
`default_nettype none

module axil_insp
    import insp_pkg::*;
#(
    parameter logic [31:0] ID_VALUE = 32'h1A57_0001
) (
    input  wire         clk,
    input  wire         rst_n,              // synchronous, active low

    // AXI4-Lite slave
    input  wire  [15:0] s_axi_awaddr,
    input  wire         s_axi_awvalid,
    output logic        s_axi_awready,
    input  wire  [31:0] s_axi_wdata,
    input  wire  [3:0]  s_axi_wstrb,
    input  wire         s_axi_wvalid,
    output logic        s_axi_wready,
    output logic [1:0]  s_axi_bresp,
    output logic        s_axi_bvalid,
    input  wire         s_axi_bready,
    input  wire  [15:0] s_axi_araddr,
    input  wire         s_axi_arvalid,
    output logic        s_axi_arready,
    output logic [31:0] s_axi_rdata,
    output logic [1:0]  s_axi_rresp,
    output logic        s_axi_rvalid,
    input  wire         s_axi_rready,

    // settings (clk domain; crossed to clk_pix in top.sv)
    output meas_cfg_t   o_cfg,
    output logic        o_ovl_en,
    output logic        o_bin_view,
    output logic [2:0]  o_verdict,
    output logic [10:0] o_cx,
    output logic [10:0] o_cy,

    // from the pixel side
    input  meas_res_t   i_bank0,            // clk_pix registers, see header
    input  meas_res_t   i_bank1,
    input  wire         i_done_toggle,      // clk_pix, toggles once per result set
    input  wire         i_sof_toggle,       // clk_pix, toggles once per video frame
    input  wire         i_video_locked      // asynchronous
);

    localparam logic [15:0] A_ID = 16'h000, A_CTRL = 16'h004, A_THRESH = 16'h008, A_WPOS = 16'h00C,
                            A_WSIZE = 16'h010, A_STATUS = 16'h014, A_FCNT = 16'h018, A_PIXF = 16'h01C,
                            A_RA = 16'h040, A_RSX = 16'h044, A_RSY = 16'h048, A_RSXXL = 16'h04C,
                            A_RSXXH = 16'h050, A_RSYYL = 16'h054, A_RSYYH = 16'h058, A_RSXYL = 16'h05C,
                            A_RSXYH = 16'h060, A_RBU = 16'h064, A_RBV = 16'h068, A_RFID = 16'h06C,
                            A_OVLV = 16'h080, A_OVLC = 16'h084;

    // ---- settings registers ---------------------------------------------------------------
    // Initial values = reset values, so the settings crossing never sends all-zero settings while clk_acc
    // starts and rst_n is still low (review finding R2).
    localparam logic [31:0] CTRL_RST   = 32'h0000_0007;                                 // POL, FILT_EN, OVERLAY_EN
    localparam logic [31:0] THRESH_RST = {24'd0, CFG_DEFAULT.thresh};
    localparam logic [31:0] WPOS_RST   = {5'd0, CFG_DEFAULT.y0, 5'd0, CFG_DEFAULT.x0};
    localparam logic [31:0] WSIZE_RST  = {5'd0, CFG_DEFAULT.h,  5'd0, CFG_DEFAULT.w};
    logic [31:0] ctrl_q = CTRL_RST, thresh_q = THRESH_RST, wpos_q = WPOS_RST, wsize_q = WSIZE_RST;
    logic [31:0] ovlv_q = '0, ovlc_q = '0;

    assign o_cfg = '{x0: wpos_q[10:0], y0: wpos_q[26:16], w: wsize_q[10:0], h: wsize_q[26:16],
                     thresh: thresh_q[7:0], pol: ctrl_q[0], filt_en: ctrl_q[1]};
    assign o_ovl_en   = ctrl_q[2];
    assign o_bin_view = ctrl_q[3];
    assign o_verdict  = ovlv_q[2:0];
    assign o_cx       = ovlc_q[10:0];
    assign o_cy       = ovlc_q[26:16];

    function automatic logic [31:0] apply_strb(input logic [31:0] old, input logic [31:0] data,
                                               input logic [3:0] strb);
        for (int i = 0; i < 4; i++) if (strb[i]) old[8*i +: 8] = data[8*i +: 8];
        return old;
    endfunction

    // ---- write channel ----------------------------------------------------------------------
    logic aw_hs;
    assign aw_hs         = s_axi_awvalid && s_axi_wvalid && !s_axi_bvalid;
    assign s_axi_awready = aw_hs;
    assign s_axi_wready  = aw_hs;
    assign s_axi_bresp   = 2'b00;          // OKAY

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            ctrl_q       <= CTRL_RST;
            thresh_q     <= THRESH_RST;
            wpos_q       <= WPOS_RST;
            wsize_q      <= WSIZE_RST;
            ovlv_q       <= '0;
            ovlc_q       <= '0;
            s_axi_bvalid <= 1'b0;
        end else begin
            if (aw_hs) begin
                unique case ({s_axi_awaddr[15:2], 2'b00})
                    A_CTRL:   ctrl_q   <= apply_strb(ctrl_q,   s_axi_wdata, s_axi_wstrb) & 32'h0000_000F;
                    A_THRESH: thresh_q <= apply_strb(thresh_q, s_axi_wdata, s_axi_wstrb) & 32'h0000_00FF;
                    A_WPOS:   wpos_q   <= apply_strb(wpos_q,   s_axi_wdata, s_axi_wstrb) & 32'h07FF_07FF;
                    A_WSIZE:  wsize_q  <= apply_strb(wsize_q,  s_axi_wdata, s_axi_wstrb) & 32'h07FF_07FF;
                    A_OVLV:   ovlv_q   <= apply_strb(ovlv_q,   s_axi_wdata, s_axi_wstrb) & 32'h0000_0007;
                    A_OVLC:   ovlc_q   <= apply_strb(ovlc_q,   s_axi_wdata, s_axi_wstrb) & 32'h07FF_07FF;
                    default: ;                                              // read-only or reserved
                endcase
                s_axi_bvalid <= 1'b1;
            end else if (s_axi_bvalid && s_axi_bready) begin
                s_axi_bvalid <= 1'b0;
            end
        end
    end

    // ---- events from the pixel side ---------------------------------------------------------
    (* ASYNC_REG = "TRUE" *) logic [1:0] done_sync_q = '0, sof_sync_q = '0, lock_sync_q = '0;
    logic        done_last_q = 1'b0, sof_last_q = 1'b0;
    logic        bank_q = 1'b1;
    logic [31:0] frame_cnt_q = '0, pix_frames_q = '0;

    always_ff @(posedge clk) begin
        done_sync_q <= {done_sync_q[0], i_done_toggle};
        sof_sync_q  <= {sof_sync_q[0],  i_sof_toggle};
        lock_sync_q <= {lock_sync_q[0], i_video_locked};
        done_last_q <= done_sync_q[1];
        sof_last_q  <= sof_sync_q[1];
        // The pixel side flips wr_bank and done_toggle together (both start at 0), so the bank written
        // last is always ~done_toggle. The pointer is derived from it, not counted: it can never get out
        // of step, not even when this side is reset while video runs (review finding B1). It changes in the
        // same clock as frame_cnt_q below.
        bank_q <= ~done_sync_q[1];
        if (!rst_n) begin
            frame_cnt_q  <= '0;
            pix_frames_q <= '0;
        end else begin
            if (done_sync_q[1] != done_last_q) frame_cnt_q <= frame_cnt_q + 1'b1;
            if (sof_sync_q[1] != sof_last_q) pix_frames_q <= pix_frames_q + 1'b1;
        end
    end

    meas_res_t r;                          // the newest complete result set (stable, see header)
    assign r = bank_q ? i_bank1 : i_bank0;

    // ---- read channel ------------------------------------------------------------------------
    assign s_axi_arready = !s_axi_rvalid;
    assign s_axi_rresp   = 2'b00;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            s_axi_rvalid <= 1'b0;
            s_axi_rdata  <= '0;
        end else begin
            if (s_axi_arvalid && s_axi_arready) begin
                s_axi_rvalid <= 1'b1;
                unique case ({s_axi_araddr[15:2], 2'b00})
                    A_ID:     s_axi_rdata <= ID_VALUE;
                    A_CTRL:   s_axi_rdata <= ctrl_q;
                    A_THRESH: s_axi_rdata <= thresh_q;
                    A_WPOS:   s_axi_rdata <= wpos_q;
                    A_WSIZE:  s_axi_rdata <= wsize_q;
                    A_STATUS: s_axi_rdata <= {30'd0, lock_sync_q[1], bank_q};
                    A_FCNT:   s_axi_rdata <= frame_cnt_q;
                    A_PIXF:   s_axi_rdata <= pix_frames_q;
                    A_RA:     s_axi_rdata <= 32'(r.a);
                    A_RSX:    s_axi_rdata <= 32'(r.sx);
                    A_RSY:    s_axi_rdata <= 32'(r.sy);
                    A_RSXXL:  s_axi_rdata <= r.sxx[31:0];
                    A_RSXXH:  s_axi_rdata <= 32'(r.sxx[38:32]);
                    A_RSYYL:  s_axi_rdata <= r.syy[31:0];
                    A_RSYYH:  s_axi_rdata <= 32'(r.syy[37:32]);
                    A_RSXYL:  s_axi_rdata <= r.sxy[31:0];
                    A_RSXYH:  s_axi_rdata <= 32'(r.sxy[37:32]);
                    A_RBU:    s_axi_rdata <= {5'd0, r.umax, 5'd0, r.umin};
                    A_RBV:    s_axi_rdata <= {5'd0, r.vmax, 5'd0, r.vmin};
                    A_RFID:   s_axi_rdata <= frame_cnt_q;
                    A_OVLV:   s_axi_rdata <= ovlv_q;
                    A_OVLC:   s_axi_rdata <= ovlc_q;
                    default:  s_axi_rdata <= 32'd0;           // reserved
                endcase
            end else if (s_axi_rvalid && s_axi_rready) begin
                s_axi_rvalid <= 1'b0;
            end
        end
    end

endmodule

`default_nettype wire
