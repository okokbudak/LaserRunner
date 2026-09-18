from typing import Tuple, Dict
from .base import Kinematics

class AWDCoreXYKinematics(Kinematics):
    """
    AWD (All-Wheel Drive) 4 Motorlu CoreXY Kinematiği.
    Her kayış hattı 2 bağımsız motor ile sürülür (Top-tier yüksek ivmeli sistemler).
    M1: A1 Motoru (Delta X + Delta Y)
    M2: B1 Motoru (Delta X - Delta Y)
    M3: A2 Motoru (A1 ile senkron)
    M4: B2 Motoru (B1 ile senkron)
    """
    def __init__(self, steps_per_mm: Dict[str, float]):
        super().__init__(steps_per_mm)

    def cartesian_to_actuators(
        self, dx_mm: float, dy_mm: float, dz_mm: float = 0.0
    ) -> Tuple[int, int, int, int, int]:
        spm = self.steps_per_mm.get("xy", 80.0)

        da_mm = dx_mm + dy_mm
        db_mm = dx_mm - dy_mm

        raw_a = da_mm * spm
        raw_b = db_mm * spm

        dir_bits = 0
        if raw_a > 0:
            dir_bits |= 0x01 # A1
            dir_bits |= 0x04 # A2
        if raw_b > 0:
            dir_bits |= 0x02 # B1
            dir_bits |= 0x08 # B2

        steps_a = int(round(abs(raw_a)))
        steps_b = int(round(abs(raw_b)))

        return steps_a, steps_b, steps_a, steps_b, dir_bits

    def actuators_to_cartesian(
        self, steps_m1: int, steps_m2: int, steps_m3: int, steps_m4: int
    ) -> Tuple[float, float, float]:
        spm = self.steps_per_mm.get("xy", 80.0)

        da = steps_m1 / spm
        db = steps_m2 / spm

        x = (da + db) / 2.0
        y = (da - db) / 2.0
        return x, y, 0.0
