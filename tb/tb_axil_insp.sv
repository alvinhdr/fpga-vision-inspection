// =============================================================================
// File   : tb_axil_insp.sv
// Project: Real-Time FPGA Vision Inspection Station
// Purpose: Self-checking test of rtl/axil_insp.sv (AXI4-Lite register block):
//          reset values, register write/read and masks, settings outputs, and the result-bank logic:
//          after each "done" toggle from the pixel side, FRAME_CNT counts and the result words come
//          from the bank that was written last. Two clocks (100 MHz AXI, 74.25 MHz pixel) are used.
//          Prints "TEST PASSED" or "TEST FAILED".
// =============================================================================
`timescale 1ns/1ps
`default_nettype none

module tb_axil_insp;
    import insp_pkg::*;

    logic clk = 0, clk_pix = 0, rst_n = 0;
    always #5     clk     = ~clk;        // 100 MHz
    always #6.734 clk_pix = ~clk_pix;    // 74.25 MHz

    logic [15:0] awaddr = 0, araddr = 0;
    logic [31:0] wdata = 0, rdata;
    logic [3:0]  wstrb = 4'hF;
    logic        awvalid = 0, wvalid = 0, bready = 1, arvalid = 0, rready = 1;
    logic        awready, wready, bvalid, arready, rvalid;
    logic [1:0]  bresp, rresp;

    meas_cfg_t   cfg;
    logic        ovl_en, bin_view;
    logic [2:0]  verdict;
    logic [10:0] cx, cy;
    meas_res_t   bank0 = '0, bank1 = '0;
    logic        done_tog = 0, sof_tog = 0;

    axil_insp dut (
        .clk(clk), .rst_n(rst_n),
        .s_axi_awaddr(awaddr), .s_axi_awvalid(awvalid), .s_axi_awready(awready),
        .s_axi_wdata(wdata), .s_axi_wstrb(wstrb), .s_axi_wvalid(wvalid), .s_axi_wready(wready),
        .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready),
        .s_axi_araddr(araddr), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
        .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(rready),
        .o_cfg(cfg), .o_ovl_en(ovl_en), .o_bin_view(bin_view), .o_verdict(verdict), .o_cx(cx), .o_cy(cy),
        .i_bank0(bank0), .i_bank1(bank1), .i_done_toggle(done_tog), .i_sof_toggle(sof_tog),
        .i_video_locked(1'b1)
    );

    int errors = 0;

    task automatic axi_write(input logic [15:0] a, input logic [31:0] d);
        @(posedge clk);
        awaddr <= a; wdata <= d; awvalid <= 1; wvalid <= 1;
        do @(posedge clk); while (!(awready && wready));
        awvalid <= 0; wvalid <= 0;
        do @(posedge clk); while (!bvalid);
    endtask

    task automatic axi_read(input logic [15:0] a, output logic [31:0] d);
        @(posedge clk);
        araddr <= a; arvalid <= 1;
        do @(posedge clk); while (!arready);
        arvalid <= 0;
        while (!rvalid) @(posedge clk);
        d = rdata;
        @(posedge clk);
    endtask

    task automatic check(input logic [15:0] a, input logic [31:0] exp, input string what);
        logic [31:0] d;
        axi_read(a, d);
        if (d !== exp) begin
            $display("ERROR %s: addr 0x%03h read 0x%08h expected 0x%08h", what, a, d, exp);
            errors++;
        end
    endtask

    // pixel side: write a result into the bank that will be read next, then toggle "done"
    logic wr_bank = 0;
    task automatic pix_done(input meas_res_t r);
        @(posedge clk_pix);
        if (wr_bank) bank1 <= r; else bank0 <= r;
        wr_bank  <= ~wr_bank;
        done_tog <= ~done_tog;
        repeat (8) @(posedge clk);            // let the toggle cross
    endtask

    function automatic meas_res_t mk(input int k);
        meas_res_t r;
        r.a = 20'(1000 + k); r.sx = 30'(123456 + k); r.sy = 29'(65432 + k);
        r.sxx = 39'h55_1234_5678 + 39'(k); r.syy = 38'h2A_8765_4321 + 38'(k); r.sxy = 38'h15_0F0F_0F0F + 38'(k);
        r.umin = 11'(10 + k); r.umax = 11'(200 + k); r.vmin = 11'(20 + k); r.vmax = 11'(300 + k);
        return r;
    endfunction

    task automatic check_result(input meas_res_t r, input int fcnt);
        check(16'h018, 32'(fcnt), "FRAME_CNT");
        check(16'h06C, 32'(fcnt), "R_FRAME_ID");
        check(16'h040, 32'(r.a), "R_A");
        check(16'h044, 32'(r.sx), "R_SX");
        check(16'h048, 32'(r.sy), "R_SY");
        check(16'h04C, r.sxx[31:0], "R_SXX_LO");
        check(16'h050, 32'(r.sxx[38:32]), "R_SXX_HI");
        check(16'h054, r.syy[31:0], "R_SYY_LO");
        check(16'h058, 32'(r.syy[37:32]), "R_SYY_HI");
        check(16'h05C, r.sxy[31:0], "R_SXY_LO");
        check(16'h060, 32'(r.sxy[37:32]), "R_SXY_HI");
        check(16'h064, {5'd0, r.umax, 5'd0, r.umin}, "R_BBOX_U");
        check(16'h068, {5'd0, r.vmax, 5'd0, r.vmin}, "R_BBOX_V");
    endtask

    initial begin
        repeat (5) @(posedge clk);
        rst_n <= 1;
        repeat (3) @(posedge clk);

        // reset values
        check(16'h000, 32'h1A57_0001, "ID");
        check(16'h004, 32'h0000_0007, "CTRL reset");
        check(16'h008, 32'd120, "THRESH reset");
        check(16'h00C, {5'd0, 11'd240, 5'd0, 11'd400}, "WIN_POS reset");
        check(16'h010, {5'd0, 11'd360, 5'd0, 11'd480}, "WIN_SIZE reset");
        check(16'h018, 32'd0, "FRAME_CNT reset");
        check(16'h0F0, 32'd0, "reserved address");
        if (cfg !== CFG_DEFAULT) begin $display("ERROR o_cfg after reset"); errors++; end

        // writes, masks, outputs
        axi_write(16'h004, 32'hFFFF_FFF2);   check(16'h004, 32'h0000_0002, "CTRL mask");
        axi_write(16'h008, 32'h0000_01B4);   check(16'h008, 32'h0000_00B4, "THRESH mask");
        axi_write(16'h00C, {5'h1F, 11'd100, 5'h1F, 11'd50}); check(16'h00C, {5'd0, 11'd100, 5'd0, 11'd50}, "WIN_POS");
        axi_write(16'h010, {5'd0, 11'd200, 5'd0, 11'd300});  check(16'h010, {5'd0, 11'd200, 5'd0, 11'd300}, "WIN_SIZE");
        axi_write(16'h080, 32'd2);           check(16'h080, 32'd2, "OVL_VERDICT");
        axi_write(16'h084, {5'd0, 11'd333, 5'd0, 11'd777});  check(16'h084, {5'd0, 11'd333, 5'd0, 11'd777}, "OVL_CENTRE");
        axi_write(16'h018, 32'hDEAD);        check(16'h018, 32'd0, "FRAME_CNT is read-only");
        if (cfg.x0 != 50 || cfg.y0 != 100 || cfg.w != 300 || cfg.h != 200 || cfg.thresh != 8'hB4 ||
            cfg.pol != 0 || cfg.filt_en != 1 || ovl_en != 0 || bin_view != 0 || verdict != 2 || cx != 777 || cy != 333) begin
            $display("ERROR settings outputs"); errors++;
        end
        // byte strobe: only byte 0
        wstrb = 4'b0001; axi_write(16'h008, 32'h0000_0011); wstrb = 4'hF;
        check(16'h008, 32'h0000_0011, "THRESH byte write");

        // result banks: 5 result sets, the newest one must always be read
        for (int k = 1; k <= 5; k++) begin
            pix_done(mk(k));
            check_result(mk(k), k);
        end
        // the bank just read stays valid while the pixel side writes the OTHER bank (no toggle yet)
        @(posedge clk_pix); if (wr_bank) bank1 <= mk(99); else bank0 <= mk(99);
        repeat (4) @(posedge clk);
        check_result(mk(5), 5);

        // video frame counter
        repeat (3) begin @(posedge clk_pix); sof_tog <= ~sof_tog; repeat (8) @(posedge clk); end
        check(16'h01C, 32'd3, "PIX_FRAMES");
        check(16'h014, {30'd0, 1'b1, 1'b0}, "STATUS (locked, bank 0 after 5 sets)");

        if (errors == 0) $display("TEST PASSED");
        else             $display("TEST FAILED: %0d errors", errors);
        $finish;
    end
endmodule

`default_nettype wire
