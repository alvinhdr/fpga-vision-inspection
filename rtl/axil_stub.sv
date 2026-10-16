// =============================================================================
// File   : axil_stub.sv
// Project: Real-Time FPGA Vision Inspection Station
// Purpose: M0 placeholder AXI4-Lite slave (clk_acc, 100 MHz). Every read returns ID_VALUE,
//          every write is accepted and ignored, so the ARM can never hang on the bus.
//          Replaced by the real register map (axil_regs.sv) in M4.
// =============================================================================
`default_nettype none

module axil_stub #(
    parameter logic [31:0] ID_VALUE = 32'h1A57_0000   // project tag, M0
) (
    input  wire         clk,
    input  wire         rst_n,
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
    input  wire         s_axi_rready
);

    // Write: accept address and data together, answer OKAY one clock later.
    assign s_axi_awready = s_axi_awvalid && s_axi_wvalid && !s_axi_bvalid;
    assign s_axi_wready  = s_axi_awready;
    assign s_axi_bresp   = 2'b00;
    // Read: accept the address, return ID_VALUE one clock later.
    assign s_axi_arready = s_axi_arvalid && !s_axi_rvalid;
    assign s_axi_rresp   = 2'b00;
    assign s_axi_rdata   = ID_VALUE;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            s_axi_bvalid <= 1'b0;
            s_axi_rvalid <= 1'b0;
        end else begin
            if (s_axi_awready)     s_axi_bvalid <= 1'b1;
            else if (s_axi_bready) s_axi_bvalid <= 1'b0;
            if (s_axi_arready)     s_axi_rvalid <= 1'b1;
            else if (s_axi_rready) s_axi_rvalid <= 1'b0;
        end
    end

endmodule

`default_nettype wire
