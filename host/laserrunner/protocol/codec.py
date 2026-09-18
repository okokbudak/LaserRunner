import struct
from typing import Optional, Tuple, Dict, Any

# Senkronizasyon Bayrakları
SYNC1 = 0xAA
SYNC2 = 0x55
URGENT_ESTOP = 0xFF

# Opcode Sabitleri
CMD_PING            = 0x01
CMD_EMERGENCY_STOP  = 0x02
CMD_ENABLE_MOTORS   = 0x03
CMD_SET_LASER_POWER = 0x04
CMD_QUEUE_MOTION    = 0x05
CMD_HOME_AXIS       = 0x06
CMD_QUERY_STATUS    = 0x07
CMD_SET_AUX_OUTPUT  = 0x08  # Hava Motoru, Duman Fanı, Kırmızı Kılavuz Lazer vb.
CMD_START_HOMING    = 0x09  # Dual-Y Auto-Squaring Homing
CMD_CONFIG_TMC      = 0x0A  # TMC2209/5160 Akım ve Sensörsüz Homing Ayarları

RESP_ACK            = 0x81
RESP_STATUS         = 0x82
RESP_ERROR          = 0x83

# Yardımcı Aygıt ID'leri
AUX_AIR_ASSIST       = 0x01
AUX_EXHAUST_FAN      = 0x02
AUX_RED_POINTER      = 0x03
AUX_HEAD_COOLING_FAN = 0x04
AUX_HIGH_POWER_RELAY = 0x05
AUX_LASER2_POWER     = 0x06

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
        seq = self.next_seq()
        length = len(payload)
        crc_data = bytes([length, seq, opcode]) + payload
        crc = calculate_crc16(crc_data)
        return bytes([SYNC1, SYNC2, length, seq, opcode]) + payload + struct.pack(">H", crc)

    def encode_ping(self, timestamp_ms: int) -> bytes:
        return self.encode_frame(CMD_PING, struct.pack(">I", timestamp_ms))

    def encode_emergency_stop(self) -> bytes:
        return self.encode_frame(CMD_EMERGENCY_STOP, b"")

    def encode_enable_motors(self, bitmask: int = 0x0F) -> bytes:
        return self.encode_frame(CMD_ENABLE_MOTORS, bytes([bitmask]))

    def encode_set_laser_power(self, power: int) -> bytes:
        clamped = max(0, min(4095, int(power)))
        return self.encode_frame(CMD_SET_LASER_POWER, struct.pack(">H", clamped))

    def encode_set_aux_output(self, device_id: int, value: int) -> bytes:
        """
        Yardımcı çıkışları kontrol eder:
        device_id: 1 (Air Assist), 2 (Exhaust Fan), 3 (Red Pointer), vb.
        value: 0 (OFF), 1 (ON) veya PWM duty (0-255 / 0-4095)
        """
        payload = struct.pack(">BH", device_id, int(value))
        return self.encode_frame(CMD_SET_AUX_OUTPUT, payload)

    def encode_start_homing(self, axis_mask: int = 0x03) -> bytes:
        """bit 0: X, bit 1: Dual-Y (Auto Squaring), bit 2: Z"""
        return self.encode_frame(CMD_START_HOMING, bytes([axis_mask]))

    def encode_config_tmc(
        self,
        motor_id: int,
        mode: int,
        run_current_ma: int,
        hold_current_ma: int,
        microsteps: int,
        interpolate: bool,
        stealthchop_threshold_speed: int = 0,
        sg_thresh: int = 65
    ) -> bytes:
        """
        TMC sürücü çalışma modunu (SpreadCycle/StealthChop/Hybrid), akım ve StallGuard ayarlarını kodlar.
        mode: 0 = SpreadCycle (Maksimum tork), 1 = StealthChop (Sessiz), 2 = Hybrid
        """
        payload = struct.pack(
            ">BBHHHBHB",
            motor_id,
            mode,
            int(run_current_ma),
            int(hold_current_ma),
            int(microsteps),
            1 if interpolate else 0,
            int(stealthchop_threshold_speed),
            int(sg_thresh)
        )
        return self.encode_frame(CMD_CONFIG_TMC, payload)

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
        if payload_opcode == RESP_ACK:
            seq_id, free_slots = struct.unpack("<BB", payload[:2])
            return {"type": "ACK", "seq_id": seq_id, "free_slots": free_slots}
        
        elif payload_opcode == RESP_STATUS:
            # Genişletilmiş Durum Paketi Unpack (24 Bayt)
            if len(payload) >= 24:
                uptime, pos_x, pos_y, pos_z, pwr, free_slots, flags, temp_x10, s_flags, endstops = struct.unpack(
                    "<IiiiHBBhBB", payload[:24]
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
                    "is_estop": bool(flags & 0x04),
                    "diode_temp_c": round(temp_x10 / 10.0, 1),
                    "lid_open": bool(s_flags & 0x01),
                    "flame_alert": bool(s_flags & 0x02),
                    "air_assist": bool(s_flags & 0x04),
                    "red_pointer": bool(s_flags & 0x08),
                    "endstops": endstops
                }
            else:
                # Geriye dönük uyumluluk
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
