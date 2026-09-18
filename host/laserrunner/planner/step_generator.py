import math
from typing import Dict, Any, Optional
from ..kinematics.base import Kinematics
from .trajectory import TrajectorySegment

class StepGenerator:
    def __init__(self, kinematics: Kinematics):
        self.kinematics = kinematics

    def segment_to_motion_block(self, segment: TrajectorySegment) -> Optional[Dict[str, Any]]:
        """
        TrajectorySegment nesnesini STM32 Firmware MotionBlock yapısına dönüştürür.
        """
        steps_x, steps_y1, steps_y2, steps_z, dir_bits = self.kinematics.cartesian_to_actuators(
            segment.dx_mm, segment.dy_mm, segment.dz_mm
        )

        total_steps = max(steps_x, steps_y1, steps_y2, steps_z)
        if total_steps == 0:
            return None

        # Hızlara göre adım aralıkları (mikrosaniye)
        # v = mesafe / zaman -> interval = duration / total_steps
        dist = math.sqrt(segment.dx_mm**2 + segment.dy_mm**2 + segment.dz_mm**2)
        if dist < 0.0001:
            return None

        def speed_to_interval_us(speed: float) -> int:
            if speed <= 0.1:
                return 10000  # Çok düşük hızda 10ms
            step_rate = (speed / dist) * total_steps
            if step_rate <= 0:
                return 10000
            interval_us = int(round(1_000_000.0 / step_rate))
            return max(5, min(65535, interval_us))

        start_interval = speed_to_interval_us(segment.start_speed)
        end_interval = speed_to_interval_us(segment.end_speed)

        return {
            "total_steps": total_steps,
            "steps_x": steps_x,
            "steps_y1": steps_y1,
            "steps_y2": steps_y2,
            "steps_z": steps_z,
            "dir_bits": dir_bits,
            "start_interval_us": start_interval,
            "end_interval_us": end_interval,
            "laser_power_start": segment.start_power,
            "laser_power_end": segment.end_power
        }
