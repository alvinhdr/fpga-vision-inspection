"""
modbus_mini.py - a small Modbus TCP server and client, written from the protocol description (no library).
Project: Real-Time FPGA Vision Inspection Station

Modbus TCP frame = 7-byte MBAP header + PDU:
    MBAP: transaction id (2) | protocol id = 0 (2) | length = bytes after this field (2) | unit id (1)
    PDU : function code (1) | data
Supported function codes: 1 read coils, 3 read holding registers, 4 read input registers (same table as 3),
5 write single coil, 6 write single register, 16 write multiple registers.
Errors answer with function code + 0x80 and an exception code (1 illegal function, 2 illegal address, 3 illegal value).
All registers are unsigned 16 bit. Used by py/plc_gateway.py (server) and py/plc_sim.py (client).
"""
import socket
import socketserver
import struct
import threading

TABLE_SIZE = 200


class ModbusData:
    """The registers and coils of the server; thread safe."""

    def __init__(self):
        self.regs = [0] * TABLE_SIZE
        self.coils = [False] * TABLE_SIZE
        self.lock = threading.Lock()

    def set_reg(self, addr, value):
        with self.lock:
            self.regs[addr] = int(value) & 0xFFFF

    def get_reg(self, addr):
        with self.lock:
            return self.regs[addr]

    def get_coil(self, addr):
        with self.lock:
            return self.coils[addr]

    def set_coil(self, addr, value):
        with self.lock:
            self.coils[addr] = bool(value)


def handle_pdu(pdu, data, on_write=None):
    """PDU in -> PDU out (pure function, easy to test)."""
    fc = pdu[0]
    try:
        if fc in (3, 4):
            addr, count = struct.unpack(">HH", pdu[1:5])
            if not 1 <= count <= 125:
                return bytes([fc | 0x80, 3])
            if addr + count > TABLE_SIZE:
                return bytes([fc | 0x80, 2])
            with data.lock:
                vals = data.regs[addr:addr + count]
            return bytes([fc, 2 * count]) + struct.pack(f">{count}H", *vals)
        if fc == 1:
            addr, count = struct.unpack(">HH", pdu[1:5])
            if not 1 <= count <= 2000:
                return bytes([fc | 0x80, 3])
            if addr + count > TABLE_SIZE:
                return bytes([fc | 0x80, 2])
            with data.lock:
                bits = data.coils[addr:addr + count]
            out = bytearray((count + 7) // 8)
            for i, b in enumerate(bits):
                if b:
                    out[i // 8] |= 1 << (i % 8)
            return bytes([fc, len(out)]) + bytes(out)
        if fc == 5:
            addr, val = struct.unpack(">HH", pdu[1:5])
            if val not in (0x0000, 0xFF00):
                return bytes([fc | 0x80, 3])
            if addr >= TABLE_SIZE:
                return bytes([fc | 0x80, 2])
            data.set_coil(addr, val == 0xFF00)
            if on_write:
                on_write("coil", addr, val == 0xFF00)
            return pdu[:5]
        if fc == 6:
            addr, val = struct.unpack(">HH", pdu[1:5])
            if addr >= TABLE_SIZE:
                return bytes([fc | 0x80, 2])
            data.set_reg(addr, val)
            if on_write:
                on_write("reg", addr, val)
            return pdu[:5]
        if fc == 16:
            addr, count, nbytes = struct.unpack(">HHB", pdu[1:6])
            if not 1 <= count <= 123 or nbytes != 2 * count:
                return bytes([fc | 0x80, 3])
            if addr + count > TABLE_SIZE:
                return bytes([fc | 0x80, 2])
            for i, v in enumerate(struct.unpack(f">{count}H", pdu[6:6 + nbytes])):
                data.set_reg(addr + i, v)
                if on_write:
                    on_write("reg", addr + i, v)
            return pdu[:5]
    except struct.error:
        return bytes([fc | 0x80, 3])
    return bytes([fc | 0x80, 1])


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        data, on_write = self.server.mb_data, self.server.on_write
        buf = b""
        while True:
            try:
                chunk = self.request.recv(260)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while len(buf) >= 8:                                   # MBAP (7) + at least a function code
                tid, pid, length, unit = struct.unpack(">HHHB", buf[:7])
                if len(buf) < 6 + length:
                    break
                pdu, buf = buf[7:6 + length], buf[6 + length:]
                if pid != 0 or not pdu:
                    return                                         # not Modbus: drop the connection
                resp = handle_pdu(pdu, data, on_write)
                self.request.sendall(struct.pack(">HHHB", tid, 0, len(resp) + 1, unit) + resp)


class ModbusServer:
    def __init__(self, host="127.0.0.1", port=5020, on_write=None):
        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.data = ModbusData()
        self._srv = socketserver.ThreadingTCPServer((host, port), _Handler)
        self._srv.daemon_threads = True
        self._srv.mb_data = self.data
        self._srv.on_write = on_write
        self.port = self._srv.server_address[1]
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._srv.shutdown()
        self._srv.server_close()


class ModbusError(Exception):
    pass


class ModbusClient:
    def __init__(self, host="127.0.0.1", port=5020, unit=1, timeout=2.0):
        self.unit, self.tid = unit, 0
        self.sock = socket.create_connection((host, port), timeout=timeout)

    def close(self):
        self.sock.close()

    def _call(self, pdu):
        self.tid = (self.tid + 1) & 0xFFFF
        self.sock.sendall(struct.pack(">HHHB", self.tid, 0, len(pdu) + 1, self.unit) + pdu)
        head = self._recv(7)
        tid, pid, length, unit = struct.unpack(">HHHB", head)
        body = self._recv(length - 1)
        if tid != self.tid:
            raise ModbusError("transaction id mismatch")
        if body[0] & 0x80:
            raise ModbusError(f"exception {body[1]} for function {body[0] & 0x7F}")
        return body

    def _recv(self, n):
        out = b""
        while len(out) < n:
            c = self.sock.recv(n - len(out))
            if not c:
                raise ModbusError("connection closed")
            out += c
        return out

    def read_holding(self, addr, count):
        b = self._call(struct.pack(">BHH", 3, addr, count))
        return list(struct.unpack(f">{count}H", b[2:2 + 2 * count]))

    def read_coils(self, addr, count):
        b = self._call(struct.pack(">BHH", 1, addr, count))
        return [bool(b[2 + i // 8] >> (i % 8) & 1) for i in range(count)]

    def write_coil(self, addr, value):
        self._call(struct.pack(">BHH", 5, addr, 0xFF00 if value else 0))

    def write_register(self, addr, value):
        self._call(struct.pack(">BHH", 6, addr, value & 0xFFFF))
