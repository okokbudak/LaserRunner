import struct
from typing import Optional, Tuple, Dict, Any

# Senkronizasyon Bayrakları
SYNC1 = 0xAA
SYNC2 = 0x55
URGENT_ESTOP = 0xFF

# Opcode Sabitleri
CMD_PING = 0x01
CMD_EMERGENCY_STOP = 0x02
CMD_ENABLE_MOTORS = 0x03
CMD_SET_LASER_POWER = 0x04
CMD_QUEUE_MOTION = 0x05
CMD_HOME_AXIS = 0x06
CMD_QUERY_STATUS = 0x07

RESP_ACK = 0x81
RESP_STATUS = 0x82
RESP_ERROR = 0x83

def calculate_crc16(data: bytes) -> int:
    """CRC16-CCITT hesaplama (Polinom: 0x1021, Başlangıç: 0xFFFF)"""
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

class ProtocolCodec:
    def __init__(self):
        self.seq_id = 0

    def next_seq(self) -> int:
        current = self.seq_id
        self.seq_id = (self.seq_id + 1) & 0xFF
        return current

    def encode_frame(self, opcode: int, payload: bytes = b"") -> bytes:
        """Standart bir protokol paketi üretir."""
        seq = self.next_seq()
        length = len(payload)
        
        # CRC Sync hariç hesaplanır: (length, seq, opcode, payload)
        crc_data = bytes([length, seq, opcode]) + payload
        crc = calculate_crc16(crc_data)
        
        frame = bytes([SYNC1, SYNC2, length, seq, opcode]) + payload + struct.pack(">H", crc)
        return frame

    def encode_ping(self, timestamp_ms: int) -> bytes:
        payload = struct.pack(">I", timestamp_ms)
        return self.encode_frame(CMD_PING, payload)

    def encode_emergency_stop(self) -> bytes:
        return self.encode_frame(CMD_EMERGENCY_STOP, b"")

    def encode_enable_motors(self, bitmask: int = 0x0F) -> bytes:
        return self.encode_frame(CMD_ENABLE_MOTORS, bytes([bitmask]))

    def encode_set_laser_power(self, power: int) -> bytes:
        """Manuel lazer gücü (0 - 4095)"""
        clamped = max(0, min(4095, int(power)))
        payload = struct.pack(">H", clamped)
        return self.encode_frame(CMD_SET_LASER_POWER, payload)

    def encode_motion_block(
        self,
        total_steps: int,
        steps_x: int,
        steps_y1: int,
        steps_y2: int,
        steps_z: int,
        dir_bits: int,
        start_interval_us: int,
        end_interval_us: int,
        laser_power_start: int,
        laser_power_end: int
    ) -> bytes:
        """
        Hareket Bloğu Paketi (22 bayt):
        <I: total_steps (4B)
        <H: steps_x (2B)
        <H: steps_y1 (2B)
        <H: steps_y2 (2B)
        <H: steps_z (2B)
        <B: dir_bits (1B)
        <H: start_interval_us (2B)
        <H: end_interval_us (2B)
        <H: laser_power_start (2B)
        <H: laser_power_end (2B)
        """
        payload = struct.pack(
            "<IHHHHBHHHH",
            total_steps,
            steps_x,
            steps_y1,
            steps_y2,
            steps_z,
            dir_bits,
            start_interval_us,
            end_interval_us,
            laser_power_start,
            laser_power_end
        )
        return self.encode_frame(CMD_QUEUE_MOTION, payload)

    def encode_query_status(self) -> bytes:
        return self.encode_frame(CMD_QUERY_STATUS, b"")

    @staticmethod
    def decode_packet(payload_opcode: int, payload: bytes) -> Dict[str, Any]:
        """Firmware'den gelen yanıt paketini çözümler."""
        if payload_opcode == RESP_ACK:
            seq_id, free_slots = struct.unpack("<BB", payload[:2])
            return {"type": "ACK", "seq_id": seq_id, "free_slots": free_slots}
        
        elif payload_opcode == RESP_STATUS:
            uptime, pos_x, pos_y, pos_z, pwr, free_slots, flags = struct.unpack(
                "<IiiiHBB", payload[:21]
            )
            return {
                "type": "STATUS",
                "uptime_ms": uptime,
                "pos_x": pos_x,
                "pos_y": pos_y,
                "pos_z": pos_z,
                "laser_pwm": pwr,
                "free_slots": free_slots,
                "is_running": bool(flags & 0x02),
                "is_estop": bool(flags & 0x04)
            }
        
        elif payload_opcode == RESP_ERROR:
            err_code, detail = struct.unpack("<BB", payload[:2])
            return {"type": "ERROR", "code": err_code, "detail": detail}
        
        return {"type": "UNKNOWN", "opcode": payload_opcode, "data": payload}
