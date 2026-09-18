import time
import threading
from typing import List, Dict, Any, Optional

from ..kinematics.base import Kinematics
from ..kinematics.cartesian import CartesianKinematics
from ..kinematics.corexy import CoreXYKinematics
from ..kinematics.awd_corexy import AWDCoreXYKinematics
from ..planner.trajectory import TrajectoryPlanner
from ..planner.step_generator import StepGenerator
from ..planner.macro_engine import MacroEngine
from ..planner.homing_sequence import HomingSequenceManager
from ..planner.input_shaper import InputShaper
from .verification import VerificationManager
from .config_manager import ConfigManager
from ..protocol.codec import (
    AUX_AIR_ASSIST,
    AUX_EXHAUST_FAN,
    AUX_RED_POINTER,
    AUX_HEAD_COOLING_FAN,
    AUX_HIGH_POWER_RELAY
)
from .transport import SerialTransport

class MachineState:
    DISCONNECTED = "DISCONNECTED"
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FRAMING = "FRAMING"
    HOMING = "HOMING"
    PAUSED = "PAUSED"
    ESTOP = "ESTOP"

class LaserRunnerController:
    """
    LaserRunner Merkezi Kontrol Motoru.
    Gelişmiş eklentiler (Air assist, duman fanı, 3.3V kılavuz lazer,
    güvenlik sensörleri, Dual-Y Auto-Squaring homing, Klipper makroları,
    Rezonans telafi / Input Shaping ve donanım doğrulamaları) tam entegredir.
    """
    def __init__(
        self,
        kinematics_type: str = "cartesian",
        steps_per_mm: Optional[Dict[str, float]] = None,
        acceleration: float = 3000.0,
        port: str = "COM3"
    ):
        self.config_manager = ConfigManager()
        
        # rotation_distance veya steps_per_mm yapılandırması
        if steps_per_mm is None:
            steps_per_mm = self.config_manager.get_steps_per_mm()

        self.kinematics_type = kinematics_type
        self.kinematics = self._build_kinematics(kinematics_type, steps_per_mm)
        self.planner = TrajectoryPlanner(acceleration_mm_s2=acceleration)
        self.step_generator = StepGenerator(self.kinematics)
        self.transport = SerialTransport(port=port)

        # Klipper Uyumlu Alt Modüller
        self.macro_engine = MacroEngine(self)
        self.macro_engine.load_macros_from_config(self.config_manager.get_macros())
        
        self.homing_sequence = HomingSequenceManager(self, self.macro_engine)
        self.homing_sequence.configure_override(self.config_manager.get_homing_override())

        self.input_shaper = InputShaper(self.config_manager.get_input_shaper_config())
        self.verification = VerificationManager(self, self.config_manager)

        self.state = MachineState.DISCONNECTED
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.pos_z = 0.0
        
        # Canlı Donanım ve Sensör Durumları
        self.diode_temperature = 25.0
        self.lid_open = False
        self.flame_alert = False
        self.air_assist_active = False
        self.red_pointer_active = False
        self.exhaust_fan_duty = 0
        self.endstop_states = 0
        self.endstops_mask = 0

        self.job_progress = 0.0
        self.is_aborting = False
        self._job_thread: Optional[threading.Thread] = None

        # Telemetri callback'i
        self.transport.on_status_callback = self._on_telemetry
        self.transport.on_disconnect_callback = self._on_hardware_disconnected

    def _on_hardware_disconnected(self):
        print("[Controller] Donanım bağlantısı koptu (USB çıkarıldı veya port kapandı)!")
        self.state = MachineState.DISCONNECTED
        self.transport.free_slots = 0

    def _build_kinematics(self, ktype: str, spm: Dict[str, float]) -> Kinematics:
        ktype = ktype.lower()
        if ktype == "corexy":
            return CoreXYKinematics(spm)
        elif ktype == "awd_corexy":
            return AWDCoreXYKinematics(spm)
        else:
            return CartesianKinematics(spm, dual_y=True)

    def connect(self, port: Optional[str] = None) -> bool:
        if port:
            self.transport.port = port
        if self.transport.connect():
            self.state = MachineState.IDLE
            time.sleep(0.2)
            self.apply_tmc_configurations()
            self.enable_motors(True)
            return True
        self.state = MachineState.DISCONNECTED
        return False

    def apply_tmc_configurations(self):
        """laserrunner.cfg dosyasındaki TMC2209 ayarlarını mikrodenetleyiciye gönderir."""
        tmc_drivers = self.config_manager.get_tmc_drivers()
        axis_map = {
            "stepper_x": 0,
            "stepper_y": 1,
            "stepper_y1": 2,
            "stepper_z": 3,
            "stepper_a": 4
        }
        for stepper_name, cfg in tmc_drivers.items():
            motor_id = axis_map.get(stepper_name)
            if motor_id is not None:
                run_ma = int(cfg.get("run_current", 0.8) * 1000)
                hold_ma = int(cfg.get("hold_current", 0.4) * 1000)
                mode = int(cfg.get("mode_code", 0))
                microsteps = int(cfg.get("microsteps", 16))
                interpolate = bool(cfg.get("interpolate", True))
                stealth_speed = int(cfg.get("stealthchop_threshold", 0))
                sg_thresh = int(cfg.get("sgthrs", 65))
                self.configure_tmc_driver(
                    motor_id=motor_id,
                    run_current_ma=run_ma,
                    hold_current_ma=hold_ma,
                    microsteps=microsteps,
                    mode=mode,
                    interpolate=interpolate,
                    stealthchop_threshold_speed=stealth_speed,
                    sg_thresh=sg_thresh
                )
                time.sleep(0.02)

    def configure_tmc_driver(
        self,
        motor_id: int,
        run_current_ma: int,
        hold_current_ma: int,
        microsteps: int = 16,
        mode: int = 0,
        interpolate: bool = True,
        stealthchop_threshold_speed: int = 0,
        sg_thresh: int = 65
    ):
        frame = self.transport.codec.encode_config_tmc(
            motor_id=motor_id,
            mode=mode,
            run_current_ma=run_current_ma,
            hold_current_ma=hold_current_ma,
            microsteps=microsteps,
            interpolate=interpolate,
            stealthchop_threshold_speed=stealthchop_threshold_speed,
            sg_thresh=sg_thresh
        )
        self.transport.send_raw(frame)
        print(f"[Controller] TMC Motor {motor_id} parametreleri yüklendi: {run_current_ma}mA, {microsteps}uStep, mod={mode}")

    def disconnect(self):
        self.set_air_assist(False)
        self.set_red_pointer(False)
        self.set_exhaust_fan(0)
        self.enable_motors(False)
        self.transport.disconnect()
        self.state = MachineState.DISCONNECTED

    def enable_motors(self, enable: Any = True):
        if self.state == MachineState.ESTOP and enable:
            self.is_aborting = False
            self.state = MachineState.IDLE
        if isinstance(enable, bool):
            bitmask = 0x0F if enable else 0x00
        elif isinstance(enable, int):
            bitmask = enable & 0x0F
        else:
            bitmask = 0x0F if enable else 0x00
        frame = self.transport.codec.encode_enable_motors(bitmask)
        self.transport.send_raw(frame)

    def emergency_stop(self):
        self.is_aborting = True
        self.state = MachineState.ESTOP
        self.transport.send_emergency_stop()

    def reset_estop(self):
        self.is_aborting = False
        if self.transport.is_connected:
            self.state = MachineState.IDLE
            self.enable_motors(True)
        else:
            self.state = MachineState.DISCONNECTED
        print("[Controller] Acil durdurma sıfırlandı, makine IDLE durumuna geçti.")

    def set_manual_laser(self, power_percent: float):
        """Manuel ana lazer açma / kapama (Odaklama için)"""
        if self.lid_open and power_percent > 0:
            print("[Güvenlik] Kapak açıkken lazer ateşlenemez!")
            return
        raw_pwr = int((power_percent / 100.0) * 4095)
        frame = self.transport.codec.encode_set_laser_power(raw_pwr)
        self.transport.send_raw(frame)

    # ==========================================
    # YARDIMCI DONANIM VE EKLENTİ KONTROLLERİ
    # ==========================================
    def set_air_assist(self, active: bool):
        """Hava Motoru / Solenoid Valf (M7/M8/M9)"""
        self.air_assist_active = active
        frame = self.transport.codec.encode_set_aux_output(AUX_AIR_ASSIST, 1 if active else 0)
        self.transport.send_raw(frame)

    def set_exhaust_fan(self, duty_0_to_255: int):
        """Duman Tahliye Emiş Fanı PWM (0 - 255)"""
        self.exhaust_fan_duty = max(0, min(255, int(duty_0_to_255)))
        frame = self.transport.codec.encode_set_aux_output(AUX_EXHAUST_FAN, self.exhaust_fan_duty)
        self.transport.send_raw(frame)

    def set_red_pointer(self, active: bool):
        """3.3V Kılavuz / Çerçeveleme Kırmızı Nokta Lazer"""
        self.red_pointer_active = active
        frame = self.transport.codec.encode_set_aux_output(AUX_RED_POINTER, 1 if active else 0)
        self.transport.send_raw(frame)

    def start_homing(self, axis_mask: int = 0x03, use_sequence: bool = True):
        """
        Dual-Y Auto-Squaring Destekli Homing veya [homing_override] Sekansı:
        axis_mask: bit 0: X, bit 1: Dual-Y, bit 2: Z
        """
        if self.state not in (MachineState.IDLE, MachineState.PAUSED):
            return

        if use_sequence and hasattr(self, "homing_sequence") and self.homing_sequence.override_config:
            axes = ""
            if axis_mask & 0x01: axes += "x"
            if axis_mask & 0x02: axes += "y"
            if axis_mask & 0x04: axes += "z"
            self.homing_sequence.execute_homing(axes or "xy")
            return

        self.state = MachineState.HOMING
        frame = self.transport.codec.encode_start_homing(axis_mask)
        self.transport.send_raw(frame)
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.state = MachineState.IDLE

    def jog(self, dx: float, dy: float, dz: float = 0.0, speed_mm_s: float = 40.0):
        """Elle eksen hareketi (Jog)"""
        if self.state == MachineState.ESTOP:
            raise RuntimeError("Makine ACİL DURDURMA (ESTOP) durumunda! Önce FIRMWARE_RESTART veya ESTOP Sıfırla yapın.")
        if self.state not in (MachineState.IDLE, MachineState.PAUSED):
            raise RuntimeError(f"Makine bu durumda hareket edemez: {self.state}")

        segments = self.planner.plan_move(
            dx=dx, dy=dy, dz=dz,
            target_speed=speed_mm_s,
            target_power=0,
            dynamic_laser=False
        )

        for seg in segments:
            block = self.step_generator.segment_to_motion_block(seg)
            if block:
                self.transport.send_motion_block(block)

        self.pos_x += dx
        self.pos_y += dy
        self.pos_z += dz

    def run_job_async(self, moves: List[Dict[str, Any]], framing: bool = False, use_air_assist: bool = True):
        """Takım yolunu arka planda yürütür."""
        if self.state != MachineState.IDLE:
            return

        self.is_aborting = False
        self.state = MachineState.FRAMING if framing else MachineState.RUNNING

        # İş başlangıcında otomatik hava ve duman fanını aç
        if not framing:
            if use_air_assist:
                self.set_air_assist(True)
            self.set_exhaust_fan(255) # Duman fanı tam güç

        self._job_thread = threading.Thread(
            target=self._job_worker,
            args=(moves, framing, use_air_assist),
            daemon=True
        )
        self._job_thread.start()

    def _job_worker(self, moves: List[Dict[str, Any]], framing: bool, use_air_assist: bool):
        total_moves = len(moves)
        for i, move in enumerate(moves):
            if self.is_aborting or self.lid_open or self.flame_alert:
                break

            target_x = move.get("x", self.pos_x)
            target_y = move.get("y", self.pos_y)
            target_z = move.get("z", self.pos_z)
            speed = move.get("speed", 30.0)
            power = move.get("power", 0)

            dx = target_x - self.pos_x
            dy = target_y - self.pos_y
            dz = target_z - self.pos_z

            if abs(dx) > 0.0001 or abs(dy) > 0.0001 or abs(dz) > 0.0001:
                segments = self.planner.plan_move(
                    dx=dx, dy=dy, dz=dz,
                    target_speed=speed,
                    target_power=power,
                    dynamic_laser=(power > 0)
                )

                for seg in segments:
                    if self.is_aborting or self.lid_open:
                        break
                    block = self.step_generator.segment_to_motion_block(seg)
                    if block:
                        self.transport.send_motion_block(block)

                self.pos_x = target_x
                self.pos_y = target_y
                self.pos_z = target_z

            self.job_progress = ((i + 1) / total_moves) * 100.0

        self.state = MachineState.IDLE
        self.set_manual_laser(0)

        # İş bitince hava motorunu kapat
        if not framing and use_air_assist:
            self.set_air_assist(False)
            # Duman tahliyesi için duman fanı 15 saniye daha açık kalabilir

    def _on_telemetry(self, packet: Dict[str, Any]):
        """Donanımdan gelen genişletilmiş telemetriyi işler."""
        if "diode_temp_c" in packet:
            self.diode_temperature = packet["diode_temp_c"]
        if "lid_open" in packet:
            self.lid_open = packet["lid_open"]
        if "flame_alert" in packet:
            self.flame_alert = packet["flame_alert"]
            if self.flame_alert:
                self.emergency_stop()
        if "air_assist" in packet:
            self.air_assist_active = packet["air_assist"]
        if "red_pointer" in packet:
            self.red_pointer_active = packet["red_pointer"]
        if "endstops" in packet:
            self.endstop_states = packet["endstops"]
            self.endstops_mask = packet["endstops"]
