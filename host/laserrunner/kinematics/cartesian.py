from typing import Tuple, Dict
from .base import Kinematics

class CartesianKinematics(Kinematics):
    """
    Standart Kartezyen ve Bağımsız Çift Y (Dual-Y) Kinematiği.
    M1: X Ekseni
    M2: Y1 Ekseni (Sol Motor)
    M3: Y2 Ekseni (Sağ Motor - Auto Squaring Hizalama)
    M4: Z Ekseni
    """
    def __init__(self, steps_per_mm: Dict[str, float], dual_y: bool = True):
        super().__init__(steps_per_mm)
        self.dual_y = dual_y

    def cartesian_to_actuators(
        self, dx_mm: float, dy_mm: float, dz_mm: float = 0.0
    ) -> Tuple[int, int, int, int, int]:
        spm_x = self.steps_per_mm.get("x", 80.0)
        spm_y = self.steps_per_mm.get("y", 80.0)
        spm_z = self.steps_per_mm.get("z", 400.0)

        raw_x = dx_mm * spm_x
        raw_y = dy_mm * spm_y
        raw_z = dz_mm * spm_z

        dir_bits = 0
        if raw_x > 0: dir_bits |= 0x01
        if raw_y > 0:
            dir_bits |= 0x02
            dir_bits |= 0x04 # Y2 aynı yönde döner
        if raw_z > 0: dir_bits |= 0x08

        steps_x = int(round(abs(raw_x)))
        steps_y = int(round(abs(raw_y)))
        steps_z = int(round(abs(raw_z)))

        steps_y1 = steps_y
        steps_y2 = steps_y if self.dual_y else 0

        return steps_x, steps_y1, steps_y2, steps_z, dir_bits

    def actuators_to_cartesian(
        self, steps_m1: int, steps_m2: int, steps_m3: int, steps_m4: int
    ) -> Tuple[float, float, float]:
        spm_x = self.steps_per_mm.get("x", 80.0)
        spm_y = self.steps_per_mm.get("y", 80.0)
        spm_z = self.steps_per_mm.get("z", 400.0)

        x = steps_m1 / spm_x
        y = steps_m2 / spm_y
        z = steps_m4 / spm_z
        return x, y, z
