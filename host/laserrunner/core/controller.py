import time
import threading
from typing import List, Dict, Any, Optional

from ..kinematics.base import Kinematics
from ..kinematics.cartesian import CartesianKinematics
from ..kinematics.corexy import CoreXYKinematics
from ..kinematics.awd_corexy import AWDCoreXYKinematics
from ..planner.trajectory import TrajectoryPlanner
from ..planner.step_generator import StepGenerator
from .transport import SerialTransport

class MachineState:
    DISCONNECTED = "DISCONNECTED"
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FRAMING = "FRAMING"
    PAUSED = "PAUSED"
    ESTOP = "ESTOP"

class LaserRunnerController:
    """
    LaserRunner Merkezi Kontrol Motoru.
    Kinematik, yörünge planlama ve donanım taşıma katmanlarını yönetir.
    """
    def __init__(
        self,
        kinematics_type: str = "cartesian",
        steps_per_mm: Optional[Dict[str, float]] = None,
        acceleration: float = 3000.0,
        port: str = "COM3"
    ):
        if steps_per_mm is None:
            steps_per_mm = {"x": 80.0, "y": 80.0, "z": 400.0, "xy": 80.0}

        self.kinematics_type = kinematics_type
        self.kinematics = self._build_kinematics(kinematics_type, steps_per_mm)
        self.planner = TrajectoryPlanner(acceleration_mm_s2=acceleration)
        self.step_generator = StepGenerator(self.kinematics)
        self.transport = SerialTransport(port=port)

        self.state = MachineState.DISCONNECTED
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.pos_z = 0.0
        
        self.job_progress = 0.0
        self.is_aborting = False
        self._job_thread: Optional[threading.Thread] = None

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
            # Motorları aktif et
            time.sleep(0.5)
            self.enable_motors(True)
            return True
        self.state = MachineState.DISCONNECTED
        return False

    def disconnect(self):
        self.enable_motors(False)
        self.transport.disconnect()
        self.state = MachineState.DISCONNECTED

    def enable_motors(self, enable: bool = True):
        bitmask = 0x0F if enable else 0x00
        frame = self.transport.codec.encode_enable_motors(bitmask)
        self.transport.send_raw(frame)

    def emergency_stop(self):
        self.is_aborting = True
        self.state = MachineState.ESTOP
        self.transport.send_emergency_stop()

    def set_manual_laser(self, power_percent: float):
        """Manuel lazer açma / kapama (Odaklama ve test için)"""
        raw_pwr = int((power_percent / 100.0) * 4095)
        frame = self.transport.codec.encode_set_laser_power(raw_pwr)
        self.transport.send_raw(frame)

    def jog(self, dx: float, dy: float, dz: float = 0.0, speed_mm_s: float = 40.0):
        """Elle eksen hareketi (Jog)"""
        if self.state not in (MachineState.IDLE, MachineState.PAUSED):
            return

        segments = self.planner.plan_move(
            dx=dx, dy=dy, dz=dz,
            target_speed=speed_mm_s,
            target_power=0, # Jog sırasında lazer daima kapalıdır
            dynamic_laser=False
        )

        for seg in segments:
            block = self.step_generator.segment_to_motion_block(seg)
            if block:
                self.transport.send_motion_block(block)

        self.pos_x += dx
        self.pos_y += dy
        self.pos_z += dz

    def run_job_async(self, moves: List[Dict[str, Any]], framing: bool = False):
        """Takım yolunu arka planda yürütür."""
        if self.state != MachineState.IDLE:
            return

        self.is_aborting = False
        self.state = MachineState.FRAMING if framing else MachineState.RUNNING
        self._job_thread = threading.Thread(target=self._job_worker, args=(moves,), daemon=True)
        self._job_thread.start()

    def _job_worker(self, moves: List[Dict[str, Any]]):
        total_moves = len(moves)
        for i, move in enumerate(moves):
            if self.is_aborting:
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
                    if self.is_aborting:
                        break
                    block = self.step_generator.segment_to_motion_block(seg)
                    if block:
                        self.transport.send_motion_block(block)

                self.pos_x = target_x
                self.pos_y = target_y
                self.pos_z = target_z

            self.job_progress = ((i + 1) / total_moves) * 100.0

        self.state = MachineState.IDLE
        self.set_manual_laser(0) # Güvenlik için lazeri kapat
