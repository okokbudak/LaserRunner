import math
from dataclasses import dataclass
from typing import List, Tuple
from .laser_power import LaserPowerController

@dataclass
class TrajectorySegment:
    dx_mm: float
    dy_mm: float
    dz_mm: float
    start_speed: float    # mm/s
    end_speed: float      # mm/s
    start_power: int      # 0 - 4095
    end_power: int        # 0 - 4095
    duration_s: float     # saniye

class TrajectoryPlanner:
    def __init__(self, acceleration_mm_s2: float = 3000.0):
        self.accel = acceleration_mm_s2
        self.power_controller = LaserPowerController()

    def plan_move(
        self,
        dx: float,
        dy: float,
        dz: float,
        target_speed: float,
        target_power: int,
        start_speed: float = 0.0,
        end_speed: float = 0.0,
        dynamic_laser: bool = True
    ) -> List[TrajectorySegment]:
        """
        Doğrusal bir hareketi trapezoidal (İvmelenme, Sabit Hız, Yavaşlama)
        profilli alt segmentlere ayırır.
        """
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist < 0.0001:
            return []

        # Erişilebilecek maksimum tepe hız hesabı
        # v_peak^2 = (2 * a * dist + v_start^2 + v_end^2) / 2
        max_reach_speed = math.sqrt(max(0.0, (2.0 * self.accel * dist + start_speed**2 + end_speed**2) / 2.0))
        peak_speed = min(target_speed, max_reach_speed)

        # İvmelenme ve yavaşlama mesafeleri
        accel_dist = (peak_speed**2 - start_speed**2) / (2.0 * self.accel)
        decel_dist = (peak_speed**2 - end_speed**2) / (2.0 * self.accel)
        cruise_dist = max(0.0, dist - accel_dist - decel_dist)

        segments: List[TrajectorySegment] = []

        def make_segment(length: float, v0: float, v1: float) -> TrajectorySegment:
            ratio = length / dist
            p0 = self.power_controller.calculate_power(v0, target_speed, target_power, dynamic_laser)
            p1 = self.power_controller.calculate_power(v1, target_speed, target_power, dynamic_laser)
            
            avg_v = (v0 + v1) / 2.0
            dt = length / avg_v if avg_v > 0.001 else 0.001

            return TrajectorySegment(
                dx_mm=dx * ratio,
                dy_mm=dy * ratio,
                dz_mm=dz * ratio,
                start_speed=v0,
                end_speed=v1,
                start_power=p0,
                end_power=p1,
                duration_s=dt
            )

        # 1. İvmelenme Segmenti
        if accel_dist > 0.001:
            segments.append(make_segment(accel_dist, start_speed, peak_speed))

        # 2. Sabit Hız (Cruise) Segmenti
        if cruise_dist > 0.001:
            segments.append(make_segment(cruise_dist, peak_speed, peak_speed))

        # 3. Yavaşlama Segmenti
        if decel_dist > 0.001:
            segments.append(make_segment(decel_dist, peak_speed, end_speed))

        return segments
