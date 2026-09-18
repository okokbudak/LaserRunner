from typing import Tuple, Dict
from .base import Kinematics

class CoreXYKinematics(Kinematics):
    """
    Standart CoreXY ve H-Bot Kinematiği.
    Delta A = Delta X + Delta Y (Motor 1)
    Delta B = Delta X - Delta Y (Motor 2)
    Motor 4: Z Ekseni
    """
    def __init__(self, steps_per_mm: Dict[str, float]):
        super().__init__(steps_per_mm)

    def cartesian_to_actuators(
        self, dx_mm: float, dy_mm: float, dz_mm: float = 0.0
    ) -> Tuple[int, int, int, int, int]:
        spm_x = self.steps_per_mm.get("x", 80.0)
        spm_y = self.steps_per_mm.get("y", 80.0)
        spm_z = self.steps_per_mm.get("z", 400.0)

        da_mm = dx_mm + dy_mm
        db_mm = dx_mm - dy_mm

        raw_a = da_mm * spm_x
        raw_b = db_mm * spm_y
        raw_z = dz_mm * spm_z

        dir_bits = 0
        if raw_a > 0: dir_bits |= 0x01
        if raw_b > 0: dir_bits |= 0x02
        if raw_z > 0: dir_bits |= 0x08

        steps_a = int(round(abs(raw_a)))
        steps_b = int(round(abs(raw_b)))
        steps_z = int(round(abs(raw_z)))

        return steps_a, steps_b, 0, steps_z, dir_bits

    def actuators_to_cartesian(
        self, steps_m1: int, steps_m2: int, steps_m3: int, steps_m4: int
    ) -> Tuple[float, float, float]:
        spm_x = self.steps_per_mm.get("x", 80.0)
        spm_y = self.steps_per_mm.get("y", 80.0)
        spm_z = self.steps_per_mm.get("z", 400.0)

        da = steps_m1 / spm_x
        db = steps_m2 / spm_y

        x = (da + db) / 2.0
        y = (da - db) / 2.0
        z = steps_m4 / spm_z
        return x, y, z
