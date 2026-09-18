import time
import threading
from typing import Optional, Callable, Dict, Any
import serial

from ..protocol.codec import (
    ProtocolCodec,
    SYNC1,
    SYNC2,
    URGENT_ESTOP,
    calculate_crc16
)

class SerialTransport:
    """
    RPi 4B ile Octopus Pro arasındaki yüksek hızlı USB-CDC seri iletişim yöneticisi.
    Arka plan okuma, Heartbeat pinger ve kuyruk akış kontrolünü yönetir.
    """
    def __init__(self, port: str = "COM3", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        self.codec = ProtocolCodec()

        self.free_slots = 32
        self.running = False
        self.last_rx_time = 0.0
        self.rx_thread: Optional[threading.Thread] = None
        self.heartbeat_thread: Optional[threading.Thread] = None
        
        self.on_status_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_error_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_disconnect_callback: Optional[Callable[[], None]] = None

        self._lock = threading.Lock()
        self._slot_event = threading.Event()

    def connect(self) -> bool:
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,
                write_timeout=0.5
            )
            self.running = True
            self.last_rx_time = time.time()
            
            # Alıcı iş parçacığını başlat
            self.rx_thread = threading.Thread(target=self._rx_worker, daemon=True)
            self.rx_thread.start()

            # Heartbeat (Yaşam sinyali) iş parçacığını başlat
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
            self.heartbeat_thread.start()

            print(f"[SerialTransport] Bağlandı: {self.port}")
            return True
        except Exception as e:
            print(f"[SerialTransport] Bağlantı hatası: {e}")
            return False

    def _trigger_disconnect(self):
        if not self.running:
            return
        self.running = False
        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass
            self.serial = None
        print(f"[SerialTransport] Donanım bağlantısı kesildi / port kapandı: {self.port}")
        if self.on_disconnect_callback:
            try:
                self.on_disconnect_callback()
            except Exception as e:
                print(f"[SerialTransport] Disconnect callback hatası: {e}")

    def disconnect(self):
        self.running = False
        if self.serial and self.serial.is_open:
            try:
                self.serial.close()
            except Exception:
                pass
            self.serial = None
        print("[SerialTransport] Bağlantı kesildi.")

    def send_raw(self, data: bytes):
        with self._lock:
            if self.serial and self.serial.is_open:
                try:
                    self.serial.write(data)
                    self.serial.flush()
                except (serial.SerialException, OSError, IOError) as e:
                    print(f"[SerialTransport] Yazma hatası: {e}")
                    self._trigger_disconnect()

    def send_emergency_stop(self):
        """Kuyruğa girmeden anlık 0xFF byte acil durdurma gönderir."""
        with self._lock:
            if self.serial and self.serial.is_open:
                self.serial.write(bytes([URGENT_ESTOP]))
                self.serial.flush()
        print("[SerialTransport] !!! ACİL DURDURMA GÖNDERİLDİ !!!")

    def send_motion_block(self, block_dict: Dict[str, Any], timeout_s: float = 2.0) -> bool:
        """
        Firmware kuyruğunda yer açılana kadar bekler ve hareket bloğunu gönderir.
        """
        start_t = time.time()
        while self.free_slots <= 2 and self.running:
            self._slot_event.wait(0.01)
            self._slot_event.clear()
            if time.time() - start_t > timeout_s:
                return False # Zaman aşımı

        frame = self.codec.encode_motion_block(
            total_steps=block_dict["total_steps"],
            steps_x=block_dict["steps_x"],
            steps_y1=block_dict["steps_y1"],
            steps_y2=block_dict["steps_y2"],
            steps_z=block_dict["steps_z"],
            dir_bits=block_dict["dir_bits"],
            start_interval_us=block_dict["start_interval_us"],
            end_interval_us=block_dict["end_interval_us"],
            laser_power_start=block_dict["laser_power_start"],
            laser_power_end=block_dict["laser_power_end"]
        )
        self.send_raw(frame)
        self.free_slots = max(0, self.free_slots - 1)
        return True

    def _heartbeat_worker(self):
        """Firmware donanımsal watchdog'unun tetiklenmemesi için düzenli ping atar."""
        while self.running:
            try:
                ping_frame = self.codec.encode_ping(int(time.time() * 1000) & 0xFFFFFFFF)
                self.send_raw(ping_frame)
            except Exception:
                pass
            time.sleep(0.08) # 80ms aralıklarla (Watchdog 250ms)

    def _rx_worker(self):
        """Gelen ikili paketleri ayrıştıran durum makinesi."""
        buffer = bytearray()
        while self.running:
            try:
                if not self.serial or not self.serial.is_open:
                    time.sleep(0.05)
                    continue

                chunk = self.serial.read(64)
                if chunk:
                    self.last_rx_time = time.time()
                    buffer.extend(chunk)
                else:
                    # Okuma zaman aşımı; eğer son 1.5 saniyedir hiç paket gelmediyse port koptu demektir
                    if self.running and self.last_rx_time > 0 and (time.time() - self.last_rx_time > 1.5):
                        print("[SerialTransport] Donanım zaman aşımı (USB kablosu çekilmiş olabilir)")
                        self._trigger_disconnect()
                        break
                    continue

                # Senkronizasyon ve paket arama
                while len(buffer) >= 7: # Min paket boyutu: Sync1, Sync2, Len, Seq, Opcode, CRC_H, CRC_L
                    if buffer[0] != SYNC1 or buffer[1] != SYNC2:
                        buffer.pop(0)
                        continue

                    pkt_len = buffer[2]
                    total_expected = 5 + pkt_len + 2
                    if len(buffer) < total_expected:
                        break # Paketin kalanı henüz gelmedi

                    # Paket tamamlandı, CRC doğrula
                    pkt_bytes = buffer[:total_expected]
                    crc_data = pkt_bytes[2:5 + pkt_len]
                    expected_crc = (pkt_bytes[-2] << 8) | pkt_bytes[-1]

                    if calculate_crc16(crc_data) == expected_crc:
                        opcode = pkt_bytes[4]
                        payload = pkt_bytes[5:5 + pkt_len]
                        decoded = self.codec.decode_packet(opcode, payload)
                        self._handle_incoming(decoded)
                    else:
                        print("[SerialTransport] Bozuk paket (CRC Hatası)!")

                    del buffer[:total_expected]

            except (serial.SerialException, OSError, IOError) as e:
                print(f"[SerialTransport] Seri port okuma hatası (kablo çıkarıldı): {e}")
                self._trigger_disconnect()
                break
            except Exception as e:
                time.sleep(0.05)

    def _handle_incoming(self, packet: Dict[str, Any]):
        ptype = packet.get("type")
        if ptype == "ACK":
            self.free_slots = packet.get("free_slots", 32)
            self._slot_event.set()

        elif ptype == "STATUS":
            self.free_slots = packet.get("free_slots", 32)
            self._slot_event.set()
            if self.on_status_callback:
                self.on_status_callback(packet)

        elif ptype == "ERROR":
            print(f"[Firmware ERROR] {packet}")
            if self.on_error_callback:
                self.on_error_callback(packet)
